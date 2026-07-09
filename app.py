import csv
from datetime import datetime  # 今日のおすすめ日付用
import os
import random
from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)
MEALS_FILE = "meals.csv"
RECIPES_FILE = "recipes.csv"

# ⚠️ブラウザのキャッシュで古いHTMLが表示されるのを防ぐ設定
app.config["TEMPLATES_AUTO_RELOAD"] = True


# アプリ起動時に食事履歴CSVがなければ作成する（ヘッダーのみ書き込み）
def init_meals_csv():
    if not os.path.exists(MEALS_FILE):
        with open(MEALS_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["日付", "ジャンル", "主菜", "副菜", "食費"])


# 料理マスター（recipes.csv）を読み込む関数
def load_recipes():
    recipes = []
    if os.path.exists(RECIPES_FILE):
        with open(RECIPES_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    row["price"] = int(row["price"])
                except (ValueError, TypeError):
                    continue  # 不正なデータ行はスキップする
                recipes.append(row)
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


# 💡 献立を提案するロジック
def make_suggestion(budget, genre, items_count):
    recipes = load_recipes()
    meals = load_meals()

    last_main_dish = ""
    if meals:
        last_main_dish = meals[-1].get("主菜", "")

    main_candidates = [
        r
        for r in recipes
        if r["category"] == "主菜"
        and r["genre"] == genre
        and r["menu_name"] != last_main_dish
    ]
    side_candidates = [
        r for r in recipes if r["category"] == "副菜" and r["genre"] == genre
    ]

    if not main_candidates:
        main_candidates = [
            r for r in recipes if r["category"] == "主菜" and r["genre"] == genre
        ]

    for _ in range(50):
        selected_main = (
            random.choice(main_candidates) if main_candidates else None
        )
        selected_side = (
            random.choice(side_candidates) if side_candidates else None
        )

        if not selected_main:
            return None

        total_price = selected_main["price"]
        if items_count == "2" and selected_side:
            total_price += selected_side["price"]

        if total_price <= budget:
            return {
                "genre": genre,
                "main": selected_main,
                "side": selected_side if items_count == "2" else None,
                "total_price": total_price,
            }

    return None


@app.route("/", methods=["GET", "POST"])
def index():
    suggested_menu = None
    searched = False
    
    # ⚠️ 常に最新の今日の日付を生成する
    current_today = datetime.now().strftime("%Y-%m-%d")

    if request.method == "POST":
        action = request.form.get("action")

        # 提案ボタンが押されたとき
        if action == "suggest":
            searched = True
            raw_budget = request.form.get("budget", "")
            try:
                budget = int(raw_budget) if raw_budget.strip() else 400
            except ValueError:
                budget = 400

            genre = request.form.get("genre", "和食")
            items_count = request.form.get("items_count", "2")
            suggested_menu = make_suggestion(budget, genre, items_count)

        # 「この献立を記録する」ボタンが押されたとき
        elif action == "register":
            # フォームから日付が取れない場合のバックアップとして今日の日付を設定
            date = request.form.get("date") or current_today
            genre = request.form.get("genre")
            main_dish = request.form.get("main_dish")
            side_dish = request.form.get("side_dish", "なし")
            cost = request.form.get("cost")

            with open(MEALS_FILE, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([date, genre, main_dish, side_dish, cost])

            return redirect(url_for("index"))

    meals = load_meals()

    return render_template(
        "index.html",
        meals=meals,
        suggested_menu=suggested_menu,
        searched=searched,
        today_str=current_today,  # ⚠️ 最新の日付を確実にHTMLへ送る
    )


if __name__ == "__main__":
    init_meals_csv()
    app.run(debug=True)