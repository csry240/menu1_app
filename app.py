import csv
import os
import random
from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)
MEALS_FILE = "meals.csv"
RECIPES_FILE = "recipes.csv"


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
                row["price"] = int(row["price"])  # 計算用に金額を数値にする
                recipes.append(row)
    return recipes


# 食事履歴（meals.csv）を読み込む関数 【機能1：履歴表示】
def load_meals():
    meals = []
    if os.path.exists(MEALS_FILE):
        with open(MEALS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                meals.append(row)
    return meals


# 💡 献立を提案するロジック 【機能2：スマート献立作成】
def make_suggestion(budget, genre, items_count):
    recipes = load_recipes()
    meals = load_meals()

    # 1. 前日の主菜の名前を調べる（前日と被らないようにするため）
    last_main_dish = ""
    if meals:
        last_main_dish = meals[-1]["主菜"]  # 一番最後の履歴（前日）の主菜名

    # 2. 条件（ジャンルが一致、かつ前日の主菜と名前が違う）に合う候補を絞り込む
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

    # 万が一、候補が空っぽになってしまった場合は、前日と同じ主菜も許可（エラー対策）
    if not main_candidates:
        main_candidates = [
            r for r in recipes if r["category"] == "主菜" and r["genre"] == genre
        ]

    # 3. 予算内に収まる組み合わせをランダムに探す（最大50回チャレンジ）
    for _ in range(50):
        selected_main = (
            random.choice(main_candidates) if main_candidates else None
        )
        selected_side = (
            random.choice(side_candidates) if side_candidates else None
        )

        if not selected_main:
            return None

        # 品数が「2品」なら主菜＋副菜、そうでなければ主菜のみの合計金額
        total_price = selected_main["price"]
        if items_count == "2" and selected_side:
            total_price += selected_side["price"]

        # 予算内に収まったら、その組み合わせを提案として決定！
        if total_price <= budget:
            return {
                "genre": genre,
                "main": selected_main,
                "side": selected_side if items_count == "2" else None,
                "total_price": total_price,
            }

    return None  # 予算が少なすぎるなど、見つからなかった場合


@app.route("/", methods=["GET", "POST"])
def index():
    suggested_menu = None

    if request.method == "POST":
        action = request.form.get("action")

        # 提案ボタンが押されたとき
        if action == "suggest":
            budget = int(request.form.get("budget", 400))
            genre = request.form.get("genre", "和食")
            items_count = request.form.get("items_count", "2")
            # 提案ロジックを実行
            suggested_menu = make_suggestion(budget, genre, items_count)

        # 「この献立を記録する」ボタンが押されたとき 【機能1：献立登録】
        elif action == "register":
            date = request.form["date"]
            genre = request.form["genre"]
            main_dish = request.form["main_dish"]
            side_dish = request.form.get("side_dish", "なし")
            cost = request.form["cost"]

            # 履歴ファイル（meals.csv）に追記
            with open(MEALS_FILE, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([date, genre, main_dish, side_dish, cost])

            return redirect(url_for("index"))

    # 画面表示用に履歴を読み込む
    meals = load_meals()

    return render_template(
        "index.html", meals=meals, suggested_menu=suggested_menu
    )


if __name__ == "__main__":
    init_meals_csv()
    app.run(debug=True)