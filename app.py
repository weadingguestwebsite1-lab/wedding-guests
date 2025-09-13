from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3

app = Flask(__name__)
app.secret_key = "supersecretkey123"

DB_FILE = "guests.db"


# -------------------- Initialize Database --------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create closeness table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS closeness (
            id INTEGER PRIMARY KEY,
            phrase TEXT NOT NULL
        )
    """)

    # Insert default phrases if not exist
    default_phrases = [
        (1, "قريب جدا"),
        (2, "صديق مقرب"),
        (3, "زميل عمل"),
        (4, "معارف")
    ]
    for id, phrase in default_phrases:
        cursor.execute(
            "INSERT OR IGNORE INTO closeness (id, phrase) VALUES (?, ?)",
            (id, phrase)
        )

    # Create guests table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            is_group INTEGER DEFAULT 0,
            group_size INTEGER DEFAULT 1,
            closs_id INTEGER NOT NULL,
            FOREIGN KEY(closs_id) REFERENCES closeness(id)
        )
    """)

    conn.commit()
    conn.close()


init_db()


# -------------------- Routes --------------------
@app.route("/", methods=["GET", "POST"])
def index():
    message = ""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if request.method == "POST":
        form_type = request.form.get("form_type", "")

        # Guest form
        if form_type == "guest_form":
            name = request.form.get("name", "").strip()
            if not name:
                message = "⚠️ الرجاء إدخال اسم الضيف!"
            else:
                is_group = int(request.form.get("is_group", 0))
                group_size = int(request.form.get("group_size", 1)) if is_group else 1
                closs_id = int(request.form.get("closeness", 4))  # default 4

                cursor.execute(
                    "INSERT INTO guests (name, is_group, group_size, closs_id) VALUES (?, ?, ?, ?)",
                    (name, is_group, group_size, closs_id)
                )
                conn.commit()
                conn.close()
                flash("✅ تم إضافة الضيف بنجاح!")
                return redirect(url_for("index"))

        # Closeness form
        elif form_type == "closs_form":
            for i in range(1, 5):
                phrase_input = request.form.get(f"clos{i}_input", "").strip()
                phrase_select = request.form.get(f"clos{i}_select", "").strip()
                phrase = phrase_input if phrase_input else phrase_select
                if phrase:
                    cursor.execute("UPDATE closeness SET phrase=? WHERE id=?", (phrase, i))
            conn.commit()
            conn.close()
            flash("✅ تم حفظ العبارات المخصصة بنجاح!")
            return redirect(url_for("index"))

    # Fetch guests
    cursor.execute("""
        SELECT g.id, g.name, g.is_group, g.group_size, c.phrase 
        FROM guests g
        JOIN closeness c ON g.closs_id = c.id
    """)
    guests = cursor.fetchall()

    # Fetch closeness phrases
    cursor.execute("SELECT id, phrase FROM closeness ORDER BY id")
    closeness = {f"clos{id}": phrase for id, phrase in cursor.fetchall()}

    # Predefined options for each closeness type
    predefined_options = {
        1: [
            "يا مرحبا رحب والقلب من اقصاه",
            "اغلى من يجي",
            "يا مرحبا يا اعز من يستاهل الترحيبه",
            "يامرحبا ماهيب مرة ولا عشرين مرة يامرحبا لين ينقطع صوتنا ويبتدي ترحيب عينا",
            "يامرحبا ترحيب يكتب بالانــوار يامرحبـا باللي يـشـرف حظـوره"
        ],
        2: [
            "اتسع صدر المكان وزاد فيكي رحابه",
            "يا هلا ومرحبا ترحيب ماله نظير",
            "ياقديم المودَّه مرحبـاً بـك",
            "مرحبا باللي لها القلب خفاق، بنت تساوي في عيوني ملايين",
            "أقبلي من صوب قلبي سلم اللّٰه هالخطاوي  كل دربٍ في حضورك لا مشيتي تشرفينه"
        ],
        3: [
            "تزينت ليلتنا بوجودك",
            "شرفتنا ونورتنا",
            "أهلا زميلتي",
            "سعداء بحضورك"
        ],
        4: [
            "تزينت ليلتنا بوجودك",
            "سعدنا بحضوركم وزادت فرحتنا بقدومكم",
            "مرحبا يا أجمل تفاصيل الليال ومرحبابك",
            "شرفتنا ونورتنا"
        ]
    }

    conn.close()
    return render_template(
        "index.html",
        message=message,
        closeness=closeness,
        guests=guests,
        predefined_options=predefined_options
    )


@app.route("/delete/<int:guest_id>")
def delete_guest(guest_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM guests WHERE id = ?", (guest_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
