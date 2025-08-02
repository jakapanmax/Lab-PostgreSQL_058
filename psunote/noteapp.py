import flask
import models
import forms

import sqlalchemy as sa
from flask import Flask, request, redirect, url_for, render_template
from models import db, Tag, Note
from sqlalchemy.orm import joinedload
from forms import NoteForm


app = flask.Flask(__name__)
app.config["SECRET_KEY"] = "This is secret key"
app.config[
    "SQLALCHEMY_DATABASE_URI"
] = "postgresql://coe:CoEpasswd@localhost:5432/coedb"

models.init_app(app)


@app.route("/")
def index():
    db = models.db
    notes = db.session.execute(
        db.select(models.Note).order_by(models.Note.title)
    ).scalars()
    return flask.render_template(
        "index.html",
        notes=notes,
    )

@app.route("/notes/create", methods=["GET", "POST"])
def notes_create():
    form = NoteForm()

    if form.validate_on_submit():
        note = models.Note()
        # แปลงค่าที่ไม่ใช่ relationship ก่อน (เช่น title, description)
        note.title = form.title.data
        note.description = form.description.data

        # จัดการ tags เอง ไม่ต้อง populate_obj tags โดยตรง
        note.tags.clear()
        for tag_name in form.tags.data:  # form.tags.data เป็น list ของ str
            tag = db.session.execute(db.select(models.Tag).filter_by(name=tag_name)).scalar_one_or_none()
            if not tag:
                tag = models.Tag(name=tag_name)
                db.session.add(tag)
            note.tags.append(tag)

        db.session.add(note)
        db.session.commit()
        return redirect(url_for("index"))

    return render_template("notes-create.html", form=form)


@app.route("/tags/<tag_name>")
def tags_view(tag_name):
    db = models.db
    tag = (
        db.session.execute(db.select(models.Tag).where(models.Tag.name == tag_name))
        .scalars()
        .first()
    )
    if not tag:
        return "Tag not found", 404

    notes = db.session.execute(
        db.select(models.Note).where(models.Note.tags.any(id=tag.id))
    ).scalars()

    # Query tags ที่ไม่มี note ใช้
    deletable_tags = db.session.execute(
        db.select(models.Tag)
        .outerjoin(models.Tag.notes)
        .group_by(models.Tag.id)
        .having(sa.func.count(models.Note.id) == 0)
    ).scalars().all()

    return flask.render_template(
        "tags-view.html",
        tag=tag,
        tag_name=tag_name,
        notes=notes,
        deletable_tags=deletable_tags  # ส่ง deletable_tags ไป
    )


@app.route("/notes/<int:note_id>/edit", methods=["GET", "POST"])
def notes_edit(note_id):
    db = models.db
    note = db.session.get(models.Note, note_id)
    if not note:
        return "Note not found", 404

    form = forms.NoteForm(obj=note)
    if form.validate_on_submit():
        # อัพเดตฟิลด์ title, description ด้วย populate_obj แต่ exclude tags
        note.title = form.title.data
        note.description = form.description.data

        # อัพเดต tags ใหม่เอง
        note.tags.clear()
        for tag_name in form.tags.data:
            tag = db.session.execute(db.select(models.Tag).where(models.Tag.name == tag_name)).scalar()
            if not tag:
                tag = models.Tag(name=tag_name)
                db.session.add(tag)
            note.tags.append(tag)

        db.session.commit()
        return flask.redirect(flask.url_for("index"))
    # เติมค่าฟิลด์ tags เป็น list กลับไปให้ฟอร์ม (join ด้วย comma)
    form.tags.data = [tag.name for tag in note.tags]

    return flask.render_template("notes-edit.html", form=form, note=note)

@app.route("/notes/<int:note_id>/delete", methods=["POST"])
def notes_delete(note_id):
    db = models.db
    note = db.session.get(models.Note, note_id)
    if note:
        db.session.delete(note)
        db.session.commit()
    return flask.redirect(flask.url_for("index"))

@app.route("/tags/<int:tag_id>/edit", methods=["GET", "POST"])
def tags_edit(tag_id):
    db = models.db
    tag = db.session.get(models.Tag, tag_id)
    if not tag:
        return "Tag not found", 404

    if flask.request.method == "POST":
        new_name = flask.request.form.get("name", "").strip()
        if new_name:
            tag.name = new_name
            db.session.commit()
            return flask.redirect(flask.url_for("tags_view", tag_name=new_name))
        else:
            error = "Tag name cannot be empty."
            return flask.render_template("tags-edit.html", tag=tag, error=error)

    return flask.render_template("tags-edit.html", tag=tag)

@app.route("/tags/delete/<int:tag_id>", methods=["POST"])
def tags_delete(tag_id):
    db = models.db
    tag = db.session.get(models.Tag, tag_id)
    if not tag:
        return "Tag not found", 404

    # ถ้า tag มีโน้ตเชื่อมอยู่
    if tag.notes:
        flask.flash("Cannot delete tag that is used in notes.")
        return flask.redirect(flask.request.referrer or flask.url_for("tags_view", tag_name=tag.name))

    # ถ้าไม่มีโน้ตเชื่อมอยู่ สามารถลบได้เลย
    db.session.delete(tag)
    db.session.commit()
    flask.flash("Tag deleted successfully.")
    # กลับไปหน้าเดิม (referrer) ถ้ามี หรือกลับไป index
    return flask.redirect(flask.request.referrer or flask.url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)