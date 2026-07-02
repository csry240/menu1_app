import csv
import os
import random
from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)
MEALS_FILE = "meals.csv"
RECIPES_FILE = "recipes.csv"

# 1食あたりの栄養素の目標基準値（一人暮らしの目安）
TARGET_CALORIE = 650     # kcal
TARGET_PROTEIN = 20      # g
TARGET_VEGETABLE = 120    # g

# アプリ起動時に食事履歴CSVがなければ作成する（ヘッダーに栄養素と食材を追加）
def init_meals_csv():
    if not os.path.exists(MEALS_FILE):
        with open(MEALS_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["日付", "ジャンル", "主菜", "副菜", "食費", "主な食材", "カロリー", "タンパク質", "野菜量"])


# 料理マスター（recipes.csv）を読み込む関数（栄養素と食材に対応）
def load_recipes():
    recipes = []
    if os.path.exists(RECIPES_FILE):
        with open(RECIPES_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    row["price"] = int(row.get("price", 0) or 0)
                    row["calorie"] = int(row.get("calorie", 0) or 0)
                    row["protein"] = int(row.get("protein", 0) or 0)
                    row["vegetable"] = int(row.get("vegetable", 0) or 0)
                    row["main_ingredient"] = row.get("main_ingredient", "その他")
                    recipes.append(row)
                except ValueError:
                    # 不正なデータ（「時価」など）が混入していた場合の堅牢性担保（TC-08対策）
                    continue
    return recipes


# 食事履歴（meals.csv）を読み込む関数
def load_meals():
    meals = []
    if os.path.exists(MEALS_FILE):
        with open(MEALS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                meals.append(row)
    return meals


# 💡 献立を提案するロジック（食材の重複回避、栄養素の計算を追加）
def make_suggestion(budget, genre, items_count):
    recipes = load_recipes()
    meals = load_meals()

    # 前日の履歴から「主菜名」「副菜名」「主菜の主な食材」を取得
    last_main_dish = ""
    last_side_dish = ""
    last_ingredient = ""
    if meals:
        last_main_dish = meals[-1].get("主菜", "")
        last_side_dish = meals[-1].get("副菜", "")
        last_ingredient = meals[-1].get("主な食材", "")

    # 【食材の幅を広げる：TC-11】ジャンル一致、前日と違うメニュー、かつ前日の「食材（豚肉・鶏肉等）」とも被らない
    main_candidates = [
        r for r in recipes
        if r["category"] == "主菜"
        and r["genre"] == genre
        and r["menu_name"] != last_main_dish
        and r["main_ingredient"] != last_ingredient
    ]
    
    # 万が一、食材縛りによって候補が空っぽになった場合は、メニューの重複回避のみに条件を緩める（エラー対策）
    if not main_candidates:
        main_candidates = [
            r for r in recipes 
            if r["category"] == "主菜" and r["genre"] == genre and r["menu_name"] != last_main_dish
        ]

    # 副菜の重複回避（前日と同じメニューを避ける）
    side_candidates = [
        r for r in recipes 
        if r["category"] == "副菜" and r["genre"] == genre and r["menu_name"] != last_side_dish
    ]
    if not side_candidates:
        side_candidates = [r for r in recipes if r["category"] == "副菜" and r["genre"] == genre]

    # 予算内に収まる組み合わせをランダムに探す（最大50回チャレンジ）
    for _ in range(50):
        selected_main = random.choice(main_candidates) if main_candidates else None
        selected_side = random.choice(side_candidates) if side_candidates else None

        if not selected_main:
            return None

        # 金額と栄養素の初期化（まずは主菜分）
        total_price = selected_main["price"]
        total_calorie = selected_main["calorie"]
        total_protein = selected_main["protein"]
        total_vegetable = selected_main["vegetable"]

        # 2品なら副菜分を合算
        if items_count == "2" and selected_side:
            total_price += selected_side["price"]
            total_calorie += selected_side["calorie"]
            total_protein += selected_side["protein"]
            total_vegetable += selected_side["vegetable"]

        # 予算内に収まったら、栄養データも含めて提案として決定！【TC-12】
        if total_price <= budget:
            return {
                "genre": genre,
                "main": selected_main,
                "side": selected_side if items_count == "2" else None,
                "total_price": total_price,
                "total_calorie": total_calorie,
                "total_protein": total_protein,
                "total_vegetable": total_vegetable,
                "main_ingredient": selected_main["main_ingredient"]
            }

    return None


@app.route("/", methods=["GET", "POST"])
def index():
    suggested_menu = None
    show_error = False  # 予算オーバー等で見つからなかったフラグ

    # 画面のセレクトボックス用に300円〜1000円まで50円刻みのリストを作成
    budget_options = list(range(300, 1001, 50))

    if request.method == "POST":
        action = request.form.get("action")

        # 提案ボタンが押されたとき
        if action == "suggest":
            try:
                budget = int(request.form.get("budget", 400))
            except ValueError:
                budget = 400  # フォールバック
                
            genre = request.form.get("genre", "和食")
            items_count = request.form.get("items_count", "2")
            
            suggested_menu = make_suggestion(budget, genre, items_count)
            if not suggested_menu:
                show_error = True

        # 「この献立を記録する」ボタンが押されたとき
        elif action == "register":
            date = request.form["date"]
            genre = request.form["genre"]
            main_dish = request.form["main_dish"]
            side_dish = request.form.get("side_dish", "なし")
            cost = request.form["cost"]
            main_ingredient = request.form["main_ingredient"]
            calorie = request.form["calorie"]
            protein = request.form["protein"]
            vegetable = request.form["vegetable"]

            # 履歴ファイル（meals.csv）に拡張された栄養素データごと追記
            with open(MEALS_FILE, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([date, genre, main_dish, side_dish, cost, main_ingredient, calorie, protein, vegetable])

            return redirect(url_for("index"))

    meals = load_meals()

    # 📊 【不足している栄養素の可視化ロジック：TC-13】
    # 過去の食事履歴の平均値を算出し、目標基準値と比較して不足を洗い出す
    shortages = []
    avg_nutrients = {"calorie": 0, "protein": 0, "vegetable": 0}
    
    if meals:
        valid_count = 0
        for m in meals:
            try:
                avg_nutrients["calorie"] += int(m.get("カロリー", 0) or 0)
                avg_nutrients["protein"] += int(m.get("タンパク質", 0) or 0)
                avg_nutrients["vegetable"] += int(m.get("野菜量", 0) or 0)
                valid_count += 1
            except ValueError:
                continue
                
        if valid_count > 0:
            avg_nutrients["calorie"] //= valid_count
            avg_nutrients["protein"] //= valid_count
            avg_nutrients["vegetable"] //= valid_count

            # 不足判定と改善アドバイス
            if avg_nutrients["calorie"] < TARGET_CALORIE:
                shortages.append(f"エネルギー（カロリー）が目標より {TARGET_CALORIE - avg_nutrients['calorie']} kcal 低めです。しっかり主食を食べましょう。")
            if avg_nutrients["protein"] < TARGET_PROTEIN:
                shortages.append(f"タンパク質が目標より {TARGET_PROTEIN - avg_nutrients['protein']} g 不足気味です。肉や魚、卵などの主菜を選んでみてください。")
            if avg_nutrients["vegetable"] < TARGET_VEGETABLE:
                shortages.append(f"野菜量が目標より {TARGET_VEGETABLE - avg_nutrients['vegetable']} g 不足しています。副菜をもう一品増やすか、具沢山の汁物がおすすめです。")

    return render_template(
        "index.html", 
        meals=meals, 
        suggested_menu=suggested_menu, 
        budget_options=budget_options,
        show_error=show_error,
        avg_nutrients=avg_nutrients,
        target_nutrients={"calorie": TARGET_CALORIE, "protein": TARGET_PROTEIN, "vegetable": TARGET_VEGETABLE},
        shortages=shortages
    )


if __name__ == "__main__":
    init_meals_csv()
    app.run(debug=True)