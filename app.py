from flask import Flask, render_template, request, redirect, url_for
import csv
import os

app = Flask(__name__)
CSV_FILE = 'meals.csv'

# アプリ起動時にCSVファイルがなければ作成し、ヘッダーを書き込む
def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['日付', 'ジャンル', '主菜', '副菜', '食費'])

@app.route('/', methods=['GET', 'POST'])
def index():
    # POST処理：フォームからの入力を受け取り、CSVに保存する
    if request.method == 'POST':
        date = request.form['date']
        genre = request.form['genre']
        main_dish = request.form['main_dish']
        side_dish = request.form['side_dish']
        cost = request.form['cost']
        
        with open(CSV_FILE, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([date, genre, main_dish, side_dish, cost])
        
        return redirect(url_for('index'))
        
    # GET処理：CSVからデータを読み込み、画面に表示する
    meals = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                meals.append(row)
                
    return render_template('index.html', meals=meals)

if __name__ == '__main__':
    init_csv()
    # 開発モードで起動
    app.run(debug=True)