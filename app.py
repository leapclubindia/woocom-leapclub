from flask import Flask, render_template, request, url_for, redirect, jsonify, make_response, g, session
from flask_sqlalchemy import SQLAlchemy
from sshtunnel import SSHTunnelForwarder
from woocommerce import API
from sqlalchemy.dialects.postgresql import UUID
from custom import filter_orders, list_order_items, get_params, get_orders_with_messages, get_csv_from_orders
from flask_datepicker import datepicker
from werkzeug.datastructures import ImmutableMultiDict
from datetime import datetime
from template_broadcast import TemplatesBroadcast
import uuid
import json
import requests
import csv
import os


app = Flask(__name__, instance_relative_config=True)
datepicker(app)

app.config.from_pyfile("config.py")

# db = SQLAlchemy(app)
wcapi = API(
    url=app.config["WOOCOMMERCE_API_URL"],
    consumer_key=app.config["WOOCOMMERCE_API_CUSTOMER_KEY"],
    consumer_secret=app.config["WOOCOMMERCE_API_CUSTOMER_SECRET"],
    version="wc/v3"
)


class User:
    def __init__(self, email, password):
        self.email = email
        self.password = password

    def __repr__(self):
        return f'<User: {self.email}>'


users = []
users.append(User(email=app.config["ADMIN_EMAIL"],
                  password=app.config["ADMIN_PASSWORD"]))


@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        user = [x for x in users if x.email == session['user_id']]
        if len(user) > 0:
            g.user = user[0]


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ""
    args = request.args.to_dict(flat=False)
    if "error" in args:
        error = args["error"][0]
    if request.method == 'POST':
        session.pop('user_id', None)
        email = request.form['email']
        password = request.form['password']
        user = [x for x in users if x.email == email]
        if len(user) > 0:
            user = user[0]
            if user.password == password:
                session['user_id'] = email
                return redirect(url_for('woocom_orders'))
            else:
                error = "Invalid User Password!"
        else:
            error = "You do not have accesss. Please contact To Admin!"
        return redirect(url_for('login', error=error))
    if "user_id" in session:
        return redirect(url_for("woocom_orders"))
    else:
        return render_template('login.html', error=error)
# class Orders(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     date_created = db.Column(db.DateTime, onupdate=datetime.datetime.utcnow())
#     date_modified = db.Column(db.DateTime, onupdate=datetime.datetime.utcnow())
#     total = db.Column(db.Float)
#     firstname = db.Column(db.String)
#     lastname = db.Column(db.String)
#     city = db.Column(db.String)
#     phone_number = db.Column(db.String)
#     address = db.Column(db.String)
#     address2 = db.Column(db.String)
#     payment_method = db.Column(db.String)
#     date_paid = db.Column(db.String)
#     whatsapp_message = db.Column(db.Text)


# @app.route("/", methods=["GET", "POST"])
# def webhooks():
#     if request.method == "GET":
#         page = request.args.get("page", 1, type=int)
#         orders = Orders.query.paginate(page=page, per_page=50)
#         return render_template("orders.html", orders=orders)
#     else:
#         data = request.get_json()
#         if data != []:
#             c_msg = "Hi - Your order is on the way.\n\nPlease check whether you are satisfied with the quality of items when you receive them. Feel free to Whatsapp me here if you have any queries.\n\nI hope you will like them. Looking forward to your feedback. :)\n\n\nHere are the order details:\n\n"
#             c_msg = c_msg + list_order_items_without_refunds(
#                 data["line_items"], o["id"]) + "*Total Amount: "+data["total"]+"*"
#             order = Orders(
#                 id=data["id"],
#                 date_created=data["date_created"],
#                 date_modified=data["date_modified"],
#                 total=data["total"],
#                 firstname=data["billing"]["first_name"],
#                 lastname=data["billing"]["last_name"],
#                 city=data["billing"]["city"],
#                 phone_number=data["billing"]["phone"],
#                 address=data["billing"]["address_1"],
#                 address2=data["billing"]["address_2"],
#                 payment_method=data["payment_method"],
#                 date_paid=data["date_paid"],
#                 whatsapp_message=c_msg
#             )
#             db.session.add(order)
#             db.session.commit()
#             return {"status": "Success..."}
#         else:
#             return {"data": "error"}
@app.route("/orders")
def woocom_orders():
    if not g.user:
        return redirect(url_for('login'))
    args = request.args.to_dict(flat=False)
    new_ids = []
    if "order_ids" in args:
        for i in args["order_ids"]:
            new_ids.append(int(i))
    args["order_ids"] = new_ids
    if "w_status" in args:
        is_w = True
        w_status = args["w_status"]
    else:
        is_w = False
        w_status = ""
    params = get_params(args)
    orders = wcapi.get("orders", params=params).json()
    f_orders = filter_orders(orders, args)
    orders = get_orders_with_messages(f_orders, wcapi)
    for o in orders:
        refunds = 0
        for r in o["refunds"]:
            refunds = refunds + float(r["total"])
        o["total_refunds"] = refunds*-1
        o["total"] = float(o["total"])
    return render_template("woocom_orders.html", orders=orders, query=args, nav_active=params["status"], is_w=is_w, w_status=w_status, page=int(params["page"]))

def send_whatsapp_msg(mobile, name, template):
    url = app.config["WATI_URL"]+"/api/v1/sendTemplateMessage/" + mobile
    if template == "hello_template":
        template_name = TemplatesBroadcast().hello_template
        broadcast_name = TemplatesBroadcast().hello_broadcast
    elif template == "feedback_template":
        template_name = TemplatesBroadcast().feedback_template
        broadcast_name = TemplatesBroadcast().feedback_broadcast
    elif template == "payment_remainder_template":
        template_name = TemplatesBroadcast().payment_remainder_template
        broadcast_name = TemplatesBroadcast().payment_remainder_broadcast
    elif template == "delivery_notification_template":
        template_name = TemplatesBroadcast().delivery_notification_template
        broadcast_name = TemplatesBroadcast().delivery_notification_broadcast
    else:
        return {"result": "error", "info": "Please Select Valid Button."}
    payload = {
        "template_name": template_name,
        "broadcast_name": broadcast_name,
        "parameters": "[{'name':'name', 'value':'"+name+"'},{'name':'manager', 'value':'Pratik'}]"
    }
    headers = {
        'Authorization': app.config["WATI_AUTHORIZATION"],
        'Content-Type': 'application/json',
    }

    response = requests.request(
        "POST", url, headers=headers, data=json.dumps(payload))

    return json.loads(response.text.encode('utf8'))


@app.route("/send_whatsapp_msg/<string:mobile_number>/<string:name>/<string:template_name>")
def send_whatsapp(mobile_number, name, template_name):
    if not g.user:
        return redirect(url_for('login'))
    args = request.args.to_dict(flat=False)
    if "page" in args:
        page = args["page"][0]
    else:
        page = page
    if "status" in args:
        nav_active = args["status"][0]
    else:
        nav_active = "any"
    result = send_whatsapp_msg(mobile_number, name, template_name)
    if result["result"] == "success":
        w_status = "Message Sent."
    else:
        w_status = result["info"]
    if nav_active != "any":
        return redirect(url_for("woocom_orders", w_status=w_status, status=nav_active, page=page))
    else:
        return redirect(url_for("woocom_orders", w_status=w_status, page=page))


@app.route('/csv', methods=["POST"])
def download_csv():
    if not g.user:
        return redirect(url_for('login'))
    data = request.form.to_dict(flat=False)
    orders = wcapi.get("orders", params=get_params(data)).json()
    csv_text = get_csv_from_orders(orders)
    filename = str(datetime.utcnow())+"-" + data["status"][0]+".csv"
    response = make_response(csv_text)
    cd = 'attachment; filename='+filename
    response.headers['Content-Disposition'] = cd
    response.mimetype = 'text/csv'

    return response


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


if __name__ == "__main__":
    # db.create_all()
    app.run()
