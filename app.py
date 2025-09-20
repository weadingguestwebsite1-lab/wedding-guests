from flask import Flask, render_template, request, redirect, url_for, flash, send_file, Response
import psycopg2
import os
import csv
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display

app = Flask(__name__)
app.secret_key = "supersecretkey123"

DB_URL = os.getenv("DATABASE_URL")


# -------------------- Connection Helper --------------------
def get_conn():
    return psycopg2.connect(DB_URL)


# -------------------- Initialize Database --------------------
def init_db():
    conn = get_conn()
    cursor = conn.cursor()

    # closeness table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS closeness (
            id SERIAL PRIMARY KEY,
            phrase TEXT NOT NULL
        )
    """)

    default_phrases = [
        (1, "قريب جدا"),
        (2, "صديق مقرب"),
        (3, "زميل عمل"),
        (4, "معارف")
    ]
    for id_, phrase in default_phrases:
        cursor.execute(
            "INSERT INTO closeness (id, phrase) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
            (id_, phrase)
        )

    # sequence backing the hashed id
    cursor.execute("""
        CREATE SEQUENCE IF NOT EXISTS public.guests_id_seq START 1 INCREMENT 1
    """)

    # guests table with TEXT hashed id (md5 of sequence value)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guests (
            id         TEXT PRIMARY KEY
                       DEFAULT md5(nextval('public.guests_id_seq'::regclass)::text),
            name       TEXT,
            is_group   INTEGER DEFAULT 0,
            group_size INTEGER DEFAULT 1,
            closs_id   INTEGER NOT NULL REFERENCES closeness(id)
        )
    """)

    # ensure lifecycle link (optional)
    cursor.execute("""
        ALTER SEQUENCE public.guests_id_seq OWNED BY guests.id
    """)

    conn.commit()
    conn.close()


init_db()
# تسجيل خط عربي
pdfmetrics.registerFont(TTFont("Arabic", "static/fonts/ar.ttf"))

# دالة لتجهيز النص العربي
def prepare_ar_text(text):
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


# -------------------- Routes --------------------
@app.route("/", methods=["GET", "POST"])
def index():
    message = ""
    conn = get_conn()
    cursor = conn.cursor()

    if request.method == "POST":
        form_type = request.form.get("form_type", "")

        if form_type == "guest_form":
            name = request.form.get("name", "").strip()
            if not name:
                message = "⚠️ الرجاء إدخال اسم الضيف!"
            else:
                is_group = int(request.form.get("is_group", 0))
                group_size = int(request.form.get("group_size", 1)) if is_group else 1
                closs_id = int(request.form.get("closeness", 4))

                # id will be auto-generated as md5(nextval(...))
                cursor.execute(
                    "INSERT INTO guests (name, is_group, group_size, closs_id) VALUES (%s, %s, %s, %s)",
                    (name, is_group, group_size, closs_id)
                )
                conn.commit()
                conn.close()
                flash("✅ تم إضافة الضيف بنجاح!")
                return redirect(url_for("index"))

        elif form_type == "closs_form":
            for i in range(1, 5):
                phrase_input = request.form.get(f"clos{i}_input", "").strip()
                phrase_select = request.form.get(f"clos{i}_select", "").strip()
                phrase = phrase_input if phrase_input else phrase_select
                if phrase:
                    cursor.execute("UPDATE closeness SET phrase=%s WHERE id=%s", (phrase, i))
            conn.commit()
            conn.close()
            flash("✅ تم حفظ العبارات المخصصة بنجاح!")
            return redirect(url_for("index"))

    cursor.execute("""
        SELECT g.id, g.name, g.is_group, g.group_size, c.phrase
        FROM guests g
        JOIN closeness c ON g.closs_id = c.id
        ORDER BY g.name NULLS LAST
    """)
    guests = cursor.fetchall()

    cursor.execute("SELECT id, phrase FROM closeness ORDER BY id")
    closeness = {f"clos{id_}": phrase for id_, phrase in cursor.fetchall()}

    predefined_options = {
        1: ["يا مرحبا رحب والقلب من اقصاه", "اغلى من يجي", "يا مرحبا يا اعز من يستاهل الترحيبه",
            "يامرحبا ماهيب مرة ولا عشرين مرة يامرحبا لين ينقطع صوتنا ويبتدي ترحيب عينا",
            "يامرحبا ترحيب يكتب بالانــوار يامرحبـا باللي يـشـرف حظـوره"],
        2: ["اتسع صدر المكان وزاد فيكي رحابه", "يا هلا ومرحبا ترحيب ماله نظير",
            "ياقديم المودَّه مرحبـاً بـك", "مرحبا باللي لها القلب خفاق، بنت تساوي في عيوني ملايين",
            "أقبلي من صوب قلبي سلم اللّٰه هالخطاوي  كل دربٍ في حضورك لا مشيتي تشرفينه"],
        3: ["تزينت ليلتنا بوجودك", "شرفتنا ونورتنا", "أهلا زميلتي", "سعداء بحضورك"],
        4: ["تزينت ليلتنا بوجودك", "سعدنا بحضوركم وزادت فرحتنا بقدومكم", "مرحبا يا أجمل تفاصيل الليال ومرحبابك",
            "شرفتنا ونورتنا"]
    }

    conn.close()
    return render_template(
        "index.html",
        message=message,
        closeness=closeness,
        guests=guests,
        predefined_options=predefined_options
    )


# Delete by hashed TEXT id
@app.route("/delete/<guest_id>")
def delete_guest(guest_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM guests WHERE id = %s", (guest_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


# 🔹 Download data as CSV
@app.route("/c")
def download_db():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
      SELECT 
    g.id,
    g.name,
    g.is_group,
    g.group_size,
    c.phrase,
    CASE 
        WHEN g.closs_id = 1 THEN 'قريب جدا'
        WHEN g.closs_id = 2 THEN 'صديق مقرب'
        WHEN g.closs_id = 3 THEN 'زميل عمل'
        WHEN g.closs_id = 4 THEN 'معارف'
    END AS type
FROM guests g
JOIN closeness c ON g.closs_id = c.id
ORDER BY g.name NULLS LAST;

    """)
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID (hash)", "Name", "Is Group", "Group Size", "pahrse","type"])
    writer.writerows(rows)

    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=guests.csv"
    return response

@app.route("/followup_pdf")
def followup_pdf():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT g.name, g.is_group, c.phrase
        FROM guests g
        JOIN closeness c ON g.closs_id = c.id
        ORDER BY c.id, g.is_group, g.name
    """)
    rows = cursor.fetchall()
    conn.close()

    # ترتيب البيانات
    grouped = {}
    for name, is_group, closeness in rows:
        if closeness not in grouped:
            grouped[closeness] = {"individuals": [], "groups": []}
        if is_group == 1:
            grouped[closeness]["groups"].append(name)
        else:
            grouped[closeness]["individuals"].append(name)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(200, y, prepare_ar_text("قائمة المتابعة"))
    y -= 40

    for closeness, data in grouped.items():
        pdf.setFont("Arabic", 16)
        pdf.drawString(50, y, prepare_ar_text(closeness))
        y -= 25

        # الأفراد
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(70, y, prepare_ar_text("الأفراد"))
        y -= 20
        table_data = [["الاسم", "تمت الدعوة"]]
        for name in data["individuals"]:
            table_data.append([name, " "])
        if len(table_data) > 1:
            table = Table(table_data, colWidths=[200, 100])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]))
            table.wrapOn(pdf, width, height)
            table.drawOn(pdf, 70, y - 20 * len(table_data))
            y -= 20 * (len(table_data) + 2)

        # المجموعات
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(70, y, prepare_ar_text("المجموعات"))
        y -= 20
        table_data = [["الاسم", "تمت الدعوة"]]
        for name in data["groups"]:
            table_data.append([name, " "])
        if len(table_data) > 1:
            table = Table(table_data, colWidths=[200, 100])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]))
            table.wrapOn(pdf, width, height)
            table.drawOn(pdf, 70, y - 20 * len(table_data))
            y -= 20 * (len(table_data) + 2)

        y -= 30
        if y < 100:
            pdf.showPage()
            y = height - 50

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="followup.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    # host/port as you had them
    app.run(host="0.0.0.0", port=5000, debug=True)
