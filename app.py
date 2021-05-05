from flask import Flask, render_template, request, url_for, redirect, jsonify, make_response, g, session
from flask_sqlalchemy import SQLAlchemy
from sshtunnel import SSHTunnelForwarder
from woocommerce import API
from sqlalchemy.dialects.postgresql import UUID
from custom import filter_orders, list_order_items, get_params, get_orders_with_messages, get_csv_from_orders, get_checkout_url, list_categories_with_products, list_categories, get_orders_with_wallet_balance, list_all_orders_tbd, list_created_via_with_filter, filter_orders_with_subscription, list_orders_with_status, get_csv_from_vendor_orders, get_list_to_string, get_total_from_line_items, update_order_status, get_csv_from_products, list_order_items_csv, get_totals, get_shipping_total_for_csv, get_orders_with_messages_without, get_orders_with_customer_detail, get_orders_with_supplier, list_order_refunds, get_shipping_total, list_only_refunds, list_orders_with_status_N2
from werkzeug.datastructures import ImmutableMultiDict
from template_broadcast import TemplatesBroadcast, vendor_type
from customselectlist import list_created_via, list_vendor
import uuid
import json
import requests
import csv
import os
import ast
import concurrent.futures
import time
import razorpay
from datetime import datetime, timedelta
from pytz import timezone
from slack import WebClient
from slack_bot import send_slack_message_, send_slack_message_calcelled, send_slack_for_product, send_slack_for_vendor_wise, send_every_day_at_9, vendor_wise_tbd_tomorrow, send_slack_message_dairy, send_slack_message_calcelled_dairy
from flask_crontab import Crontab
from slack_chennels import CHANNELS
from modules.universal import format_mobile, send_slack_message, get_meta_data, list_product_list_form_orders, list_customers_with_wallet_balance



app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile("config.py")
db = SQLAlchemy(app)
crontab = Crontab(app)


wcapi = API(
    url=app.config["WOOCOMMERCE_API_URL"],
    consumer_key=app.config["WOOCOMMERCE_API_CUSTOMER_KEY"],
    consumer_secret=app.config["WOOCOMMERCE_API_CUSTOMER_SECRET"],
    version="wc/v3",
    timeout=15
)

wcapi_write = API(
    url=app.config["WOOCOMMERCE_API_URL"],
    consumer_key=app.config["WOOCOMMERCE_API_CUSTOMER_KEY_WRITE"],
    consumer_secret=app.config["WOOCOMMERCE_API_CUSTOMER_SECRET_WRITE"],
    version="wc/v3",
    timeout=30
)

wcapis = API(
    url=app.config["WOOCOMMERCE_API_URL"],
    consumer_key=app.config["WOOCOMMERCE_API_CUSTOMER_KEY"],
    consumer_secret=app.config["WOOCOMMERCE_API_CUSTOMER_SECRET"],
    version="wc/v1",
    timeout=15
)

wcapiw = API(
    url=app.config["WOOCOMMERCE_API_URL"],
    consumer_key=app.config["WOOCOMMERCE_API_CUSTOMER_KEY_WALLET"],
    consumer_secret=app.config["WOOCOMMERCE_API_CUSTOMER_SECRET_WALLET"],
    version="wp/v2",
    timeout=15
)

client = WebClient(
    token=app.config["SLACK_APP_TOKEN"]
)

razorpay_client = razorpay.Client(
    auth=(app.config["RAZORPAY_ID"], app.config["RAZORPAY_SECRET"]))


class User:
    def __init__(self, email, password):
        self.email = email
        self.password = password

    def __repr__(self):
        return f'<User: {self.email}>'


users = []
users.append(User(email=app.config["ADMIN_EMAIL"],
                  password=app.config["ADMIN_PASSWORD"]))


@app.errorhandler(404)
def invalid_route(e):
    return redirect(url_for("woocom_orders"))


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


class wtmessages(db.Model):
    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    order_id = db.Column(db.Integer)
    time_sent = db.Column(db.DateTime, default=datetime.utcnow())
    template_name = db.Column(db.String)
    broadcast_name = db.Column(db.String)
    status = db.Column(db.String)


class PaymentLinks(db.Model):
    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    order_id = db.Column(db.Integer)
    receipt = db.Column(db.String)
    payment_link_url = db.Column(db.String)
    contact = db.Column(db.String)
    status = db.Column(db.String)
    name = db.Column(db.String)
    created_at = db.Column(db.String)
    amount = db.Column(db.Float)


def get_dairy_condition(o, d):
    delivery_d = datetime.strptime(d, "%Y-%m-%d")
    yesterday = delivery_d - timedelta(days=1)
    yesterday = yesterday.strftime('%Y-%m-%dT')
    vendor, manager, delivery_date, order_note,  = get_meta_data(o)
    if o['created_via'] == "subscription":
        if yesterday in o['date_created']:
            return True
        else:
            return False
    else:
        if delivery_date == d:
            return True
        else:
            return False
def filter_orders_for_errors(orders):
    new_orders = []
    for o in orders:
        vendor, manager, delivery_date, order_note,  = get_meta_data(o)
        if o['status'] in ['processing', 'pending', 'failed']:
            new_orders.append(o)
        elif vendor == "" or delivery_date == "":
            new_orders.append(o)
    return new_orders

def get_tabs_nums():
    main_dict = {}
    main_dict['failed, pending'] = {'per_page': 1,'status': "failed, pending"}
    main_dict['processing'] = {'per_page': 1,'status': "processing"}
    main_dict['tbd-paid, tbd-unpaid'] = {'per_page': 1,'status': "tbd-paid, tbd-unpaid"}
    main_dict['delivered-unpaid'] = {'per_page': 1,'status': "delivered-unpaid"}
    main_dict['completed'] = {'per_page': 1,'status': "completed"}
    main_dict['refunded'] = {'per_page': 1,'status': "refunded"}
    main_dict['cancelled'] = {'per_page': 1,'status': "cancelled"}
    main_dict['any'] = {'per_page': 1,'status': "any"}
    main_dict['subscription'] = {'per_page': 1,'status': "tbd-paid, tbd-unpaid", 'created_via': 'subscription'}
    def _get_tabs_nums(params):
        orders = wcapi.get("order2", params=main_dict[params]).headers['X-WP-Total']
        main_dict[params] = orders
    with concurrent.futures.ThreadPoolExecutor() as executor:
        result = executor.map(_get_tabs_nums, main_dict)
    return main_dict


def get_orders_for_home(args, tab):
    params = get_params(args.copy())
    if 'payment_status' in args:
        p_s = args['payment_status'].copy()
    else:
        p_s = ""
    if "created_via" in params:
        args["created_via"] = params["created_via"]
    t_orders = time.time()
    tabs_nums = get_tabs_nums()
    if 'status' in args:
        if args['status'][0] == 'dairy' and 'delivery_date' in params:
            delivery = params['delivery_date']
            del params['delivery_date']
            orders = list_orders_with_status(wcapi, params.copy())
            del params['vendor']
            params['created_via'] = "subscription"
            orders.extend(list_orders_with_status(wcapi, params.copy()))
            orders = list(
                filter(lambda o: get_dairy_condition(o, delivery), orders))
            tabs_nums['dairy'] = len(orders)
        elif args['status'][0] == 'errors':
            params['status'] = 'any'
            params['created_via'] = "admin,checkout,Order clone"
            d3 = datetime.now() - timedelta(days=3)
            d3 = str(d3.strftime('%Y-%m-%d'))+"T00:00:00"
            params['after'] = d3
            orders = list_orders_with_status(wcapi, params.copy())
            orders = filter_orders_for_errors(orders)
            tabs_nums['errors'] = len(orders)
        elif args['status'][0] == 'dairy':
            orders = list_orders_with_status(wcapi, params.copy())
            del params['vendor']
            params['created_via'] = "subscription"
            orders.extend(list_orders_with_status(wcapi, params.copy()))
            tabs_nums['dairy'] = len(orders)
        else:
            orders = wcapi.get("order2", params=params)
            tabs_nums[params['status']] = orders.headers['X-WP-Total']
            orders = orders.json()
    else:
        orders = wcapi.get("order2", params=params).json()
    orders = filter_orders(orders, args.copy())
    managers = []
    wtmessages_list = {}
    payment_links = {}
    total_payble = 0
    vendor_payble = {'dairy': 0, 'bakery': 0,
                     "grocery": 0, "personal_care": 0, '': 0}
    for o in orders:
        wallet_payment = 0
        refunds = 0
        for r in o["refunds"]:
            refunds = refunds + float(r["total"])
        o["total_refunds"] = refunds*-1
        o["total"] = float(o["total"])
        wt_messages = wtmessages.query.filter_by(order_id=o["id"]).all()
        payment_link = PaymentLinks.query.filter_by(order_id=o["id"]).all()
        if len(payment_link) > 0:
            payment_link = payment_link[-1]
        else:
            payment_link = ''
        payment_links[o["id"]] = payment_link
        wtmessages_list[o["id"]] = wt_messages
        vendor, manager, delivery_date, order_note  = get_meta_data(o)
        if len(o["fee_lines"]) > 0:
            for item in o["fee_lines"]:
                if "wallet" in item["name"].lower():
                    wallet_payment = (-1)*float(item["total"])
        if manager not in managers:
            managers.append(manager)
        if vendor in vendor_type.keys():
            o["vendor_type"] = vendor_type[vendor]
        else:
            o["vendor_type"] = ""
        o["vendor"] = vendor
        o["delivery_date"] = delivery_date
        o["order_note"] = order_note
        o["manager"] = manager
        o["wallet_payment"] = wallet_payment
        o["total"] = float(o["total"]) + float(o["wallet_payment"])
        o["checkout_url"] = get_checkout_url(o)
        total_payble += (o['total']-o['total_refunds'])
        vendor_payble[o['vendor_type']] += (o['total']-o['total_refunds'])
    if 'status_f' in args:
        params['status'] = args['status'][0]
    if "status" in args:
        if args["status"][0] == "subscription":
            params["status"] = "subscription"
        elif args['status'][0] == 'dairy':
            params['status'] = 'dairy'
            params['page'] = 1
        elif args['status'][0] == 'errors':
            params['status'] = 'errors'
        elif params['status'] in ['tbd-paid', 'tbd-unpaid']:
            params['status'] = 'tbd-paid, tbd-unpaid'
    args['payment_status'] = p_s
    return render_template("woocom_orders.html", json=json, orders=orders, query=args, nav_active=params["status"], managers=managers, vendors=list_vendor, wtmessages_list=wtmessages_list, user=g.user, list_created_via=list_created_via, page=params["page"], payment_links=payment_links, t_p=total_payble, vendor_payble=vendor_payble, tab=tab, tab_nums=tabs_nums)


@app.route("/orders")
def woocom_orders():
    if not g.user:
        return redirect(url_for('login'))
    args = request.args.to_dict(flat=False)
    return get_orders_for_home(args, tab='woocom_orders')

@app.route("/vendor_orders")
def vendor_orders():
    if not g.user:
        return redirect(url_for('login'))
    args = request.args.to_dict(flat=False)
    return get_orders_for_home(args, tab='vendor_orders')

def send_whatsapp_msg(args, mobile, name):
    url = app.config["WATI_URL"]+"/api/v1/sendTemplateMessage/" + mobile
    if name in TemplatesBroadcast.keys():
        template_name = TemplatesBroadcast[name][args["vendor_type"]]["template"]
        broadcast_name = TemplatesBroadcast[name][args["vendor_type"]]["broadcast"]
    else:
        return {"result": "error", "info": "Please Select Valid Button."}
    parameters_s = "["
    if "c_name" in args:
        args["name"] = args["c_name"]
    if "order_note" in args:
        if args["order_note"] == "":
            args["order_note"] = "No changes to the order"
    else:
        args["order_note"] = "No changes to the order"
    for d in args:
        parameters_s = parameters_s + \
            '{"name":"'+str(d)+'", "value":"'+str(args[d])+'"},'
    parameters_s = parameters_s[:-1]
    parameters_s = parameters_s+"]"
    payload = {
        "template_name": template_name,
        "broadcast_name": broadcast_name,
        "parameters": parameters_s
    }
    headers = {
        'Authorization': app.config["WATI_AUTHORIZATION"],
        'Content-Type': 'application/json',
    }

    response = requests.request(
        "POST", url, headers=headers, data=json.dumps(payload))

    result = json.loads(response.text.encode('utf8'))
    result["broadcast_name"] = broadcast_name
    result["template_name"] = template_name
    return result


@app.route("/send_whatsapp_msg/<string:name>")
def send_whatsapp(name):
    if not g.user:
        return redirect(url_for('login'))
    args = request.args.to_dict(flat=True)
    if len(args) > 0:
        if "status" in args:
            nav_active = args["status"]
        else:
            nav_active = "any"
        mobile_number = format_mobile(args["mobile_number"])
        result = send_whatsapp_msg(args, mobile_number, name)
        if result["result"] in ["success", "PENDING", "SENT", True]:
            new_wt = wtmessages(order_id=args["order_id"], template_name=result["template_name"], broadcast_name=result[
                                "broadcast_name"]["broadcastName"], status="success", time_sent=datetime.utcnow())
        else:
            new_wt = wtmessages(order_id=args["order_id"], template_name=result["template_name"], broadcast_name=result[
                                "broadcast_name"], status="failed", time_sent=datetime.utcnow())
        db.session.add(new_wt)
        db.session.commit()
        result['order_id'] = str(args['order_id'])
        return jsonify(result)


@app.route('/csv', methods=["POST"])
def download_csv():
    # Fetching Orders-------------------
    if not g.user:
        return redirect(url_for('login'))
    data = request.form.to_dict(flat=False)
    if ['action[]'][0] in data:
        data['order_ids'] = data['order_ids[]']
        data['action'] = data['action[]']
    params = get_params(data)
    params["include"] = get_list_to_string(data["order_ids"])
    c_time = time.time()
    orders = wcapi.get("orders", params=params).json()
    print("time to fetch orders: ", time.time()-c_time)

    # Collecting Meta and PopUp ready ---------------
    delivery_dates = {}
    status_list = {}
    for o in orders:
        vendor, manager, delivery_date, order_note,  = get_meta_data(o)
        if delivery_date not in delivery_dates:
            delivery_dates[delivery_date] = {"count": 1}
        else:
            delivery_dates[delivery_date]['count'] +=1
        status_t = o['status']
        if 'tbd' in status_t:
            status_t = "to-be-delivered"
        if status_t not in status_list:
            status_list[status_t] = {'count': 1}
        else:
            status_list[status_t]['count'] +=1
    
    # Conditions Download buttons........
    if data["action"][0] == "order_sheet":
        csv_text = get_csv_from_orders(orders, wcapi)
        filename = str(datetime.utcnow())+"-" + \
            data["status"][0]+"-Product-Sheet.csv"
    elif data["action"][0] == "product_sheet":
        csv_text = get_csv_from_products(orders, wcapi, 'csv')
        filename = str(datetime.utcnow())+"-" + "Product-Sheet.csv"
    # Google Sheets................
    elif data["action"][0] == 'google_sheet':
        m_time = time.time()
        c_time = time.time()
        product_list = list_product_list_form_orders(orders, wcapi)
        print("Time to fetch products: ",time.time()-c_time)
        c_time = time.time()
        for o in orders:
            refunds = []
            if len(o["refunds"]) > 0:
                refunds = wcapi.get("orders/"+str(o["id"])+"/refunds").json()
            o['line_items_text'] = list_order_items_csv(
                o["line_items"], refunds, wcapi, product_list).replace("&amp;", "&")
            o['total_text'] = get_totals(
                o["total"], refunds)+get_shipping_total_for_csv(o)
        print("Time to fetch line_items and refunds: ", time.time()-c_time)
        c_time = time.time()
        response = requests.post(
            app.config["GOOGLE_SHEET_URL"]+"?action=order_sheet", json=orders)
        print("Time to send to google sheet: ",time.time()- c_time)
        sheet_url = app.config["SHEET_URL"]+response.json()['ssUrl']
        print("Total Time: ", time.time()-m_time)
    elif data['action'][0] == 'product_google_sheet':
        o = orders[0]
        vendor, manager, delivery_date, order_note,  = get_meta_data(o)
        response = requests.post(app.config["GOOGLE_SHEET_URL"]+"?action=product_sheet", json={
                                 "products": get_csv_from_products(orders, wcapi, 'google-sheet'), "sheet_name": vendor+"_"+delivery_date})
        sheet_url = app.config["SHEET_URL"]+response.json()['ssUrl']
    elif data['action'][0] == 'delivery-google-sheet':
        o = orders[0]
        vendor, manager, delivery_date, order_note,  = get_meta_data(o)
        for order in orders:
            wallet_payment = 0
            if len(order["fee_lines"]) > 0:
                for item in order["fee_lines"]:
                    if "wallet" in item["name"].lower():
                        wallet_payment = (-1)*float(item["total"])
            order['total']= float(order['total'])+wallet_payment
        response = requests.post(app.config["GOOGLE_SHEET_URL"]+"?action=delivery_sheet", json=orders)
        sheet_url = app.config["SHEET_URL"]+response.json()['ssUrl']
    else:
        csv_text = get_csv_from_vendor_orders(orders, wcapi)
        filename = str(datetime.utcnow())+"-" + \
            data["status"][0]+"-Vendor-Order-Sheet.csv"
        response = make_response(csv_text)
        if "," in filename:
            filename = filename.replace(",", "-")
        cd = 'attachment; filename='+filename
        response.headers['Content-Disposition'] = cd
        response.mimetype = 'text/csv'
        return response
    return {'result': 'success', 'ssUrl': sheet_url, 'total_o': len(orders), 'ssName': response.json()['ssName'], "delivery_dates": delivery_dates, 'status_list': status_list}



@app.route("/download_vendor_order_csv", methods=["POST"])
def download_vendor_order_csv():
    if not g.user:
        return redirect(url_for('login'))
    data = request.form.to_dict(flat=False)
    params = {"per_page": 100}
    params["include"] = get_list_to_string(data["order_ids"])
    orders = list_orders_with_status(wcapi, params)
    csv_text = get_csv_from_vendor_orders(orders, wcapi)
    filename = str(datetime.utcnow())+"-Vendor-Order-Sheet.csv"
    response = make_response(csv_text)
    if "," in filename:
        filename = filename.replace(",", "-")
    cd = 'attachment; filename='+filename
    response.headers['Content-Disposition'] = cd
    response.mimetype = 'text/csv'
    return response


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


@app.route("/products")
def products():
    if not g.user:
        return redirect(url_for('login'))
    args = request.args.to_dict(flat=True)
    if "page" in args:
        page = args["page"]
    else:
        page = 1
    args["stock_status"] = "instock"
    args["per_page"] = 50
    products = wcapi.get("products", params=args).json()
    total_categories = list_categories(wcapi)
    return render_template("products/index.html", user=g.user, products=products, params=args, total_categories=total_categories, page=int(page))


@app.route("/list_product_categories")
def list_product_categories():
    if not g.user:
        return redirect(url_for('login'))
    args = request.args.to_dict(flat=True)
    args["stock_status"] = "instock"
    args["per_page"] = 100
    total_products = []
    page = 1
    while True:
        args["page"] = page
        products = wcapi.get("products", params=args).json()
        total_products.extend(products)
        page = page+1
        if len(products) < 100:
            break
    list_categories = list_categories_with_products(total_products)
    filename = str(datetime.utcnow())+"-" + "categories-text.txt"
    response = make_response(list_categories)
    cd = 'attachment; filename='+filename
    response.headers['Content-Disposition'] = cd
    response.mimetype = 'text/csv'
    return response


@app.route("/list_product_categories_by_c")
def list_product_categories_by_c():
    if not g.user:
        return redirect(url_for('login'))
    args = request.args.to_dict(flat=False)
    args["stock_status"] = "instock"
    args["per_page"] = 100
    total_products = []
    for c in args["categories"]:
        page = 1
        args["category"] = str(c)
        while True:
            args["page"] = page
            products = wcapi.get("products", params=args).json()
            total_products.extend(products)
            page = page+1
            if len(products) < 100:
                break
    list_categories = list_categories_with_products(total_products)
    filename = str(datetime.utcnow())+"-" + "categories-text.txt"
    response = make_response(list_categories)
    cd = 'attachment; filename='+filename
    response.headers['Content-Disposition'] = cd
    response.mimetype = 'text/csv'
    return response


def update_wati_contact_attributs(o):
    mobile_number = format_mobile(o["billing"]["phone"])
    url = app.config["WATI_URL"] + \
        "/api/v1/updateContactAttributes/" + mobile_number
    vendor, manager, delivery_date, order_note,  = get_meta_data(o)
    args = {}
    args['last_order_date'] = o["date_created"]
    args['city'] = o["shipping"]["city"]
    args["last_order_amount"] = get_total_from_line_items(o["line_items"])
    args["last_order_vendor"] = vendor
    day_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    week_day = datetime.strptime(
        o["date_created"], '%Y-%m-%dT%H:%M:%S').weekday()
    args["weekly_reminder"] = day_name[week_day]
    parameters_s = "["
    for d in args:
        parameters_s = parameters_s + \
            '{"name":"'+str(d)+'", "value":"'+str(args[d])+'"},'
    parameters_s = parameters_s[:-1]
    parameters_s = parameters_s+"]"
    payload = {"customParams": json.loads(parameters_s)}
    headers = {
        'Authorization': app.config["WATI_AUTHORIZATION"],
        'Content-Type': 'application/json',
    }

    response = requests.request(
        "POST", url, headers=headers, data=json.dumps(payload))

    result = json.loads(response.text.encode('utf8'))
    if result["result"]:
        return True


@app.route("/new_order", methods=["GET", "POST"])
def new_order():
    if request.method == "GET":
        return "Plese Use Get Method..."
    o = request.get_json()
    if o == None:
        return "Please Enter Valid Detail...."
    customer_number = format_mobile(o["billing"]["phone"])
    mobile_numbers = [customer_number]
    params = {}
    vendor, manager, delivery_date, order_note,  = get_meta_data(o)
    if vendor in vendor_type.keys():
        vendor_type1 = vendor_type[vendor]
    else:
        vendor_type1 = ""
    checkout_url = str(o["id"])+"/?pay_for_order=true&key="+str(o["order_key"])
    wallet_payment = 0
    if len(o["fee_lines"]) > 0:
        for item in o["fee_lines"]:
            if "wallet" in item["name"].lower():
                wallet_payment = (-1)*float(item["total"])
    o["total"] = float(o["total"]) + float(wallet_payment)
    params["c_name"] = o["billing"]["first_name"]
    params["order_id"] = o["id"]
    params["order_note"] = order_note
    params["total_amount"] = float(o["total"])
    params["delivery_date"] = delivery_date
    params["payment_method"] = o["payment_method_title"]
    params["delivery_charge"] = o["shipping_total"]
    params["items_amount"] = float(o["total"])-float(o["shipping_total"])
    params["order_key"] = o["order_key"]
    params["vendor_type"] = vendor_type1
    params["seller"] = vendor
    params["url_post_pay"] = checkout_url
    od = datetime.strptime(o["date_created"], '%Y-%m-%dT%H:%M:%S')
    cd = datetime.now(tz=timezone('Asia/Kolkata')).replace(tzinfo=None)
    nd = (cd - timedelta(minutes=5))
    # Sending Whatsapp Template Message....
    if request.headers["x-wc-webhook-topic"] == "order.updated":
        if (o["status"] == "processing") and (o["created_via"] == "checkout") and vendor and (od > nd):
            for num in mobile_numbers:
                if o["date_paid"] != None:
                    result = send_whatsapp_msg(params, num, "order_prepay")
                else:
                    result = send_whatsapp_msg(params, num, "order_postpay")

            if result["result"] in ["success", "PENDING", "SENT", True]:
                new_wt = wtmessages(order_id=params["order_id"], template_name=result["template_name"], broadcast_name=result[
                                    "broadcast_name"], status="success", time_sent=datetime.utcnow())
            else:
                new_wt = wtmessages(order_id=params["order_id"], template_name=result["template_name"], broadcast_name=result[
                                    "broadcast_name"], status="failed", time_sent=datetime.utcnow())
            db.session.add(new_wt)
            db.session.commit()

        # End Whatsapp Template Message.....
        # Sending Slack Message....
        if (o["status"] in ["processing", "tdb-paid", "tdb-unpaid"]) and (o["created_via"] in ["admin", "checkout"]) and (od > nd):
            if vendor in ["Mr. Dairy", "mrdairy"]:
                send_slack_message_dairy(client, wcapi, o)
            msg = send_slack_message_(client, wcapi, o)
            update_wati_contact_attributs(o)

        if (o["status"] == "cancelled"):
            if vendor in ["Mr. Dairy", "mrdairy"]:
                s_msg = send_slack_message_calcelled_dairy(client, wcapi, o)
            s_msg = send_slack_message_calcelled(client, wcapi, o)
        # End Slack Message....

    if request.headers["x-wc-webhook-topic"] == "order.created":
        if (o["created_via"] == "admin"):
            s_msg = send_slack_message_(client, wcapi, o)
            update_wati_contact_attributs(o)

    return {"Result": "Success No Error..."}


def get_subscription_wallet_balance(subscriptions):
    def _get_orders_with_wallet_balance(o):
        balance = wcapiw.get("current_balance/"+str(o["customer_id"]))
        o["wallet_balance"] = float(balance.text[1:-1])
        return o
    with concurrent.futures.ThreadPoolExecutor() as executor:
        result = executor.map(_get_orders_with_wallet_balance, subscriptions)
    return list(result)


@app.route("/subscriptions")
def subscriptions():
    if not g.user:
        return redirect(url_for('login'))
    args = request.args.to_dict(flat=True)
    if "order" in args:
        if args["order"] == 'ASC':
            order = 'DSC'
        else:
            order = 'ASC'
    else:
        order = 'ASC'
    if "page" in args:
        page = int(args["page"])
    else:
        page = 1
    args["per_page"] = 50
    t_orders = time.time()
    subscriptions = wcapis.get(
        "subscriptions", params=get_params_subscriptions(args)).json()
    t_orders = time.time()
    subscriptions = get_subscription_wallet_balance(subscriptions)
    subscriptions = sort_subscriptions(subscriptions, args, order)
    return render_template("subscriptions/index.html", user=g.user, subscriptions=subscriptions, page=page, order=order)


def get_params_subscriptions(args):
    params = {"per_page": 50}
    if "page" in args:
        params["page"] = args["page"]
    return params


def sort_subscriptions(subscriptions, args, order):
    if "sort" in args:
        if order == "ASC":
            return sorted(subscriptions, key=lambda i: i['wallet_balance'], reverse=True)
        else:
            return sorted(subscriptions, key=lambda i: i['wallet_balance'], reverse=False)
    else:
        return subscriptions


@app.route("/send_session_message/<string:order_id>")
def send_session_message(order_id):
    if not g.user:
        return redirect(url_for('login'))
    order = wcapi.get("orders/"+order_id).json()
    mobile_number = format_mobile(order["billing"]["phone"])
    order = get_orders_with_messages([order], wcapi)
    url = app.config["WATI_URL"]+"/api/v1/sendSessionMessage/" + \
        mobile_number + "?messageText="+order[0]["c_msg"]
    headers = {
        'Authorization': app.config["WATI_AUTHORIZATION"],
        'Content-Type': 'application/json',
    }
    ctime = time.time()
    response = requests.request(
        "POST", url, headers=headers)
    result = json.loads(response.text.encode('utf8'))
    if result["result"] in ["success", "PENDING", "SENT", True]:
        new_wt = wtmessages(order_id=order[0]["id"], template_name="order_detail",
                            broadcast_name="order_detail", status="success", time_sent=datetime.utcnow())
    else:
        new_wt = wtmessages(order_id=order[0]["id"], template_name="order_detail",
                            broadcast_name="order_detail", status="failed", time_sent=datetime.utcnow())
    db.session.add(new_wt)
    db.session.commit()
    result["template_name"] = 'order_detail'
    result["parameteres"] = [{'name': 'order_id', 'value': str(order_id)}]
    return jsonify(result)


@app.route("/gen_payment_link/<string:order_id>")
def gen_payment_link(order_id):
    if not g.user:
        return redirect(url_for('login'))
    args = request.args.to_dict(flat=True)
    o = wcapi.get("orders/"+order_id).json()
    orders = list_orders_with_status_N2(wcapi, {'status': 'tbd-unpaid, delivered-unpaid', 'customer': o['customer_id']})
    if len(orders)>1 and 'check' not in args:
        return jsonify({"result": 'check', 'orders':orders})
    if o['status'] in ['tbd-paid', 'completed']:
        return jsonify({'result': 'paid'})
    wallet_payment = 0
    if len(o["fee_lines"]) > 0:
        for item in o["fee_lines"]:
            if "wallet" in item["name"].lower():
                wallet_payment = (-1)*float(item["total"])
    total_amount = float(get_total_from_line_items(o["line_items"]))+float(o["shipping_total"])-wallet_payment-float(get_total_from_line_items(o["refunds"])*-1)
    total_amount = round(total_amount, 1)
    payment_links = PaymentLinks.query.filter_by(order_id=o["id"]).all()
    counter = 0
    while counter<len(payment_links):
        if float(payment_links[counter].amount) == float(total_amount)*100:
            return {"text": "Link is already exists","result": "success", 'order_id': o['id'], 'short_url': payment_links[counter].payment_link_url, 'payment': {'amount': payment_links[counter].amount, 'receipt': payment_links[counter].receipt}}
        counter += 1
    if len(payment_links)==0:
        receipt = "Leap "+str(o["id"])
    else:
        receipt = "Leap "+str(o["id"])+"-"+str(len(payment_links)+1)
    data = {
        "amount": total_amount*100,
        "receipt": receipt,
        "customer": {
            "name": o["shipping"]["first_name"] + " " + o["shipping"]["last_name"],
            "contact": format_mobile(o["billing"]["phone"])
        },
        "type": "link",
        "view_less": 1,
        "currency": "INR",
        "description": "Thank you for making a healthy and sustainable choice",
        "reminder_enable": False,
        "callback_url": "https://leapclub.in/",
        "callback_method": "get",
        "sms_notify": False,
        'email_notify': False
    }
    try:
        invoice = razorpay_client.invoice.create(data=data)
        status = "success"
        short_url = invoice['short_url']
        new_payment_link = PaymentLinks(order_id=o["id"], receipt=data["receipt"], payment_link_url=invoice['short_url'], contact=format_mobile(o["billing"]["phone"]), name=data["customer"]['name'], created_at=invoice["created_at"], amount=data['amount'], status=status)
    except Exception as e:
        status = "failed"
        short_url = ""
        new_payment_link = PaymentLinks(order_id=o["id"], receipt=data["receipt"], payment_link_url="", contact=format_mobile(o["billing"]["phone"]), name=data["customer"]['name'], created_at="", amount=data['amount'], status=status)
    db.session.add(new_payment_link)
    db.session.commit()
    return jsonify({"text": 'Success, Link Generated!',"result": status, 'payment': data, "short_url": short_url, "order_id": order_id})


@app.route("/razorpay", methods=["GET", "POST"])
def razorpay():
    if request.method == "GET":
        return "Plese Use POST Method..."
    e = request.get_json()
    if len(e) > 0:
        if e["event"] == "invoice.paid":
            if 'Wallet' in e['payload']['order']['entity']['receipt']:
                customer_id = e['payload']['order']['entity']['receipt'].split("-")[1]
                total = e['payload']['order']['entity']['amount_paid']/100
                customer = wcapi.get("customers/"+str(customer_id)).json()
                name = customer['first_name']+" "+customer['last_name']
                mobile = format_mobile(customer['billing']['phone'])
                msg = send_whatsapp_msg(
                    {'vendor_type': "any", "c_name": name}, mobile, 'payment_received')
                if 'code' not in customer:
                    refund = wcapiw.post("wallet/"+customer_id, data={'type': 'credit', 'amount': total, 'details': 'Credited by Razorpay'}).json()
                    if refund['response'] == 'success' and refund['id'] != False: 
                        response =send_slack_message(client, "PAYMENT_NOTIFICATIONS", str(total)+' added to wallet of '+customer['first_name']+" "+customer['last_name'])
                    else:
                        response =send_slack_message(client, "PAYMENT_NOTIFICATIONS", 'Error while adding money to wallet of '+customer['first_name']+" "+customer['last_name'])
            else:
                mobile = e['payload']['payment']['entity']['contact']
                order_id = e['payload']['order']['entity']['receipt'][5:].split(
                    "-")[0]
                invoice_id = e['payload']['invoice']['entity']['id']
                orders = wcapi.get("orders", params={"include": order_id})
                if orders.status_code == 200:
                    orders = orders.json()
                    order = orders[0]
                    name = order['billing']['first_name']
                    if order['status'] in ['tbd-unpaid', 'delivered-unpaid']:
                        msg = send_whatsapp_msg(
                            {'vendor_type': "any", "c_name": name}, mobile, 'payment_received')
                    for order in orders:
                        name = order['billing']['first_name']
                        vendor_name, manager, delivery_date, order_note,  = get_meta_data(order)
                        vendor_t = 'any'
                        if vendor_name in vendor_type.keys():
                            vendor_t = vendor_type[vendor_name]
                        status = update_order_status(order, invoice_id, wcapi_write)
                        if status:
                            txt_msg = "These orders are marked as paid in admin panel: "+order_id
                        else:
                            txt_msg = "These orders gave an error while marking them as paid: "+order_id
                        response =send_slack_message(client, "PAYMENT_NOTIFICATIONS", txt_msg)
            return("Done")
        else:
            return "Payment.Paid"
    else:
        return "Please enter valid detail..."


@app.route("/new_customer", methods=['POST', 'GET'])
def new_customer():
    if request.method == "GET":
        return "Plese Use POST Method..."
    e = request.get_json()
    if e:
        is_new = list(
            filter(lambda i: (i['key'] == 'wc_last_active'), e['meta_data']))
        if len(is_new) > 0:
            digits_phone = ""
            name = e['first_name']
            for i in e['meta_data']:
                if i['key'] == 'digits_phone_no':
                    digits_phone = "+91" + i['value']
                    break
            # digits_phone = "919325837420"
            msg = send_whatsapp_msg(
                {'vendor_type': "any", "c_name": name}, digits_phone, 'new-signup')
    return e


@app.route('/product_add_and_update', methods=['POST', 'GET'])
def product_add_and_update():
    if request.method == "GET":
        return "Plese Use POST Method..."
    e = request.get_json()
    topic = request.headers["x-wc-webhook-topic"]
    if e:
        send_slack_for_product(client, e, topic)
        return {"Result": "Success No Error..."}


@crontab.job(minute="30", hour="3")
# @app.route('/vendor_wise')
def vendor_wise_tbd():
    send_slack_for_vendor_wise(client, wcapi)
    return {"Result": "Success No Error..."}


# @crontab.job(minute="30", hour="15")


@app.route('/every_day_9')
def send_every_day():
    lastHourDateTime = datetime.now() - timedelta(hours=72)
    last_date = lastHourDateTime.strftime('%Y-%m-%dT%H:%M:%S')
    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow = tomorrow.strftime('%Y-%m-%d')
# all orders of processing and pending status
    params = {"per_page": 100}
    params['after'] = last_date
    params["status"] = 'processing, pending'
    params['created_via'] = 'checkout, admin, Order clone'
    orders = list_orders_with_status(wcapi, params)
    send_every_day_at_9(orders, client, "*Please change status:*\n")
# orders without vendor
    params = {"per_page": 100}
    params["status"] = 'any'
    params['after'] = last_date
    params['created_via'] = 'checkout, admin, Order clone'
    orders = list_orders_with_status(wcapi, params)
    without_vendors = []
    for o in orders:
        o['vendor'], manager, delivery_date, order_note,  = get_meta_data(o)
        if o['vendor'] == "":
            without_vendors.append(o)
    send_every_day_at_9(without_vendors, client,
                        "*Orders with vendor information missing*\n")
# orders without delivery date
    params = {"per_page": 100}
    params["status"] = 'any'
    params['after'] = last_date
    params['created_via'] = 'checkout, admin, Order clone'
    orders = list_orders_with_status(wcapi, params)
    without_date = []
    for o in orders:
        vendor, manager, delivery_date, order_note,  = get_meta_data(o)
        if delivery_date == "":
            without_date.append(o)
    send_every_day_at_9(without_date, client,
                        "*Orders with delivery date missing*\n")
# orders to be delivered tomorrow
    params = {"per_page": 100}
    params["status"] = 'tbd-unpaid, tbd-paid'
    params['created_via'] = 'checkout, admin, Order clone'
    orders = list_orders_with_status(wcapi, params)
    tbd_tomorrow = []
    for o in orders:
        vendor, manager, delivery_date, order_note,  = get_meta_data(o)
        if delivery_date == tomorrow:
            tbd_tomorrow.append(o)
    vendor_wise_tbd_tomorrow(tbd_tomorrow, client)
    return {"Result": "Success"}


@app.route("/order_details", methods=["POST"])
def order_details():
    data = request.form.to_dict(flat=False)
    data['order_ids'] = data['order_ids[]']
    params = get_params(data)
    params["include"] = get_list_to_string(data["order_ids"])
    c_time = time.time()
    orders = wcapi.get("orders", params=params).json()
    print("Time to fetch orders: ", time.time()-c_time)
    c_time = time.time()
    orders = get_orders_with_messages_without(orders, wcapi)
    print("Time to message: ", time.time()-c_time)
    main_text = ""
    total = 0
    for o in orders:
        total += float(o['total_amount'])
    for o in orders:
        main_text += o['c_msg']
        main_text += "-----------------------------------------\n\n"
    main_text += ("*Total Amount: "+str(total)+"*\n\n")
    return {"result": main_text}

@app.route("/order_details_mini", methods=["POST"])
def order_details_mini():
    data = request.form.to_dict(flat=False)
    data['order_ids'] = data['order_ids[]']
    params = get_params(data)
    params["include"] = get_list_to_string(data["order_ids"])
    orders = wcapi.get("orders", params=params).json()
    main_text = ""
    total = 0
    wallet_payment = 0
    for o in orders:
        o["total"] = float(o["total"])
        vendor, manager, delivery_date, order_note,  = get_meta_data(o)
        if len(o["fee_lines"]) > 0:
            for item in o["fee_lines"]:
                if "wallet" in item["name"].lower():
                    wallet_payment = (-1)*float(item["total"])
        o["total"] = float(o["total"]) + wallet_payment
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        if len(delivery_date)>0:
            dt = datetime.strptime(delivery_date, '%Y-%m-%d')
            d_date = dt.strftime("%A")+", "+months[dt.month-1]+" " + str(dt.day)
        else:
            d_date = ""
        main_text += ("Order ID: "+str(o['id'])+" ("+vendor_type[vendor]+")")
        main_text += ("\nDelivery Date: "+d_date)
        main_text += ("\n\nTotal Amount: "+str(o['total']))
        main_text += "\n\n-----------------------------------------\n\n"
        total +=o['total']
    main_text += ("*Total Amount: "+str(round(total,1))+"*\n\n")
    return {"result": main_text}


@app.route("/customer_details", methods=["POST"])
def customer_details():
    data = request.form.to_dict(flat=False)
    data['order_ids'] = data['order_ids[]']
    params = get_params(data)
    params["include"] = get_list_to_string(data["order_ids"])
    orders = wcapi.get("orders", params=params).json()
    orders = get_orders_with_customer_detail(orders)
    main_text = ""
    for o in orders:
        main_text += o['c_msg']
        main_text += "\n-----------------------------------------\n\n"
    return {"result": main_text}


@app.route("/supplier_messages", methods=["POST"])
def supplier_messages():
    data = request.form.to_dict(flat=False)
    data['order_ids'] = data['order_ids[]']
    params = get_params(data)
    params["include"] = get_list_to_string(data["order_ids"])
    orders = wcapi.get("orders", params=params).json()
    orders = get_orders_with_supplier(orders, wcapi)
    main_text = ""
    for o in orders:
        main_text += o['s_msg']
        main_text += "\n-----------------------------------------\n\n"
    return {"result": main_text}


@app.route("/multiple_links", methods=["POST"])
def multiple_links():
    data = request.form.to_dict(flat=False)
    data['order_ids'] = data['order_ids[]']
    params = get_params(data)
    params["include"] = get_list_to_string(data["order_ids"])
    del params['status']
    orders = wcapi.get("orders", params=params).json()
    customers = {}
    results = []
    paid_orders = []
    for o in orders:
        mobile_number = format_mobile(o['billing']['phone'])
        if mobile_number in customers:
            customers[mobile_number].append(o)
        else:
            customers[mobile_number] = [o]
        if o['status'] in ['tbd-paid', 'completed']:
            paid_orders.append(str(o['id']))
    if len(paid_orders)>0:
        return jsonify({'status': 'paid', 'result': ",".join(paid_orders)})
    for customer in customers:
        total_amount = 0
        for o in customers[customer]:
            wallet_payment = 0
            if len(o["fee_lines"]) > 0:
                for item in o["fee_lines"]:
                    if "wallet" in item["name"].lower():
                        wallet_payment = (-1)*float(item["total"])
            total_amount += (float(get_total_from_line_items(o["line_items"]))+float(
                o["shipping_total"])-wallet_payment-float(get_total_from_line_items(o["refunds"])*-1))
        o_ids = list(map(lambda o: str(o['id']), customers[customer]))
        reciept = "Leap " + \
            get_list_to_string(o_ids)
        payment_links = PaymentLinks.query.filter_by(receipt=reciept).all()
        isexists = False
        if len(payment_links) > 0:
            counter = 1
            while True:
                if len(payment_links) == 0:
                    break
                else:
                    if float(payment_links[0].amount) == float(total_amount)*100:
                        results.append({"result": "success", 'order_ids': o_ids, 'short_url': payment_links[0].payment_link_url, 'amount': payment_links[0].amount, 'receipt': reciept, "mobile":customer})
                        isexists = True
                        break
                reciept = "Leap " + \
                    get_list_to_string(o_ids)+"-"+str(counter)
                payment_links = PaymentLinks.query.filter_by(receipt=reciept).all()
                counter += 1
        if isexists:
            continue
        data1 = {
            "amount": total_amount*100,
            "receipt": reciept,
            "customer": {
                "name": o["shipping"]["first_name"] + " " + o["shipping"]["last_name"],
                "contact": customer
            },
            "type": "link",
            "view_less": 1,
            "currency": "INR",
            "description": "Thank you for making a healthy and sustainable choice",
            "reminder_enable": False,
            "callback_url": "https://leapclub.in/",
            "callback_method": "get",
            "sms_notify": False,
            'email_notify': False
        }
        try:
            invoice = razorpay_client.invoice.create(data=data1)
            status = "success"
            short_url = invoice['short_url']
            for i in o_ids:
                new_payment_link = PaymentLinks(order_id=i, receipt=data1["receipt"], payment_link_url=invoice['short_url'], contact=customer, name=data1["customer"]['name'], created_at=invoice["created_at"], amount=data1['amount'], status=status)
                db.session.add(new_payment_link)
                db.session.commit()
            results.append({"result": "success", 'order_ids': o_ids, 'short_url': invoice['short_url'], 'amount': data1['amount'], 'receipt': reciept, "mobile":customer})
        except Exception as e:
            results.append({"result": "error", 'mobile': customer, 'receipt':reciept, 'amount': data1['amount']})
    return {'results': results}


def send_session_m_st(order_id, vendor, order_note):
    order = wcapi.get("orders/"+str(order_id)).json()
    mobile_number = order["billing"]["phone"]
    order = get_orders_with_messages([order], wcapi)
    order_note_t = ""
    if order_note != "":
        order_note_t = "Please note:\n\n"+order_note+"\n\n"
    order[0]['c_msg'] = "Hi,\n\nYour "+vendor_type[vendor] + \
        " order will be delivered today. Let us know if everything meets your expectations.\n\n" + \
        order_note_t+order[0]['c_msg']
    mobile_number = mobile_number[-10:]
    mobile_number = (
        "91"+mobile_number) if len(mobile_number) == 10 else mobile_number
    url = app.config["WATI_URL"]+"/api/v1/sendSessionMessage/" + \
        mobile_number + "?messageText="+order[0]["c_msg"]
    headers = {
        'Authorization': app.config["WATI_AUTHORIZATION"],
        'Content-Type': 'application/json',
    }
    ctime = time.time()
    response = requests.request(
        "POST", url, headers=headers)
    result = json.loads(response.text.encode('utf8'))
    if result["result"] in ["success", "PENDING", "SENT", True]:
        new_wt = wtmessages(order_id=order[0]["id"], template_name="order_detail",
                            broadcast_name="order_detail", status="success", time_sent=datetime.utcnow())
        db.session.add(new_wt)
        db.session.commit()
    result["template_name"] = 'order_detail'
    result["parameteres"] = [{'name': 'order_id', 'value': str(order_id)}]
    return result

def send_whatsapp_temp_sess(args):
    args['product_type'] = args['vendor_type']
    r_s_msg = send_session_m_st(
        args['order_id'], args['seller'], args['order_note'])
    if not r_s_msg['result']:
        order_note = args["order_note"].replace("\r", "")
        order_note = order_note.replace("\n", " ")
        order_note = order_note.replace("  ", " ")
        args['order_note'] = order_note
        mobile_number = format_mobile(args["mobile_number"])
        result = send_whatsapp_msg(args, mobile_number, "delivery_today_0203")
        if result["result"] in ["success", "PENDING", "SENT", True]:
            new_wt = wtmessages(order_id=args["order_id"], template_name=result["template_name"], broadcast_name=result[
                                "broadcast_name"], status="success", time_sent=datetime.utcnow())
        else:
            new_wt = wtmessages(order_id=args["order_id"], template_name=result["template_name"], broadcast_name=result[
                                "broadcast_name"], status="failed", time_sent=datetime.utcnow())
        db.session.add(new_wt)
        db.session.commit()
        result['order_id'] = str(args['order_id'])
        return result
    r_s_msg["order_id"] = args['order_id']
    return r_s_msg


def send_whatsapp_temp(args, name):
    args['order_type'] = args['vendor_type']
    if "#" in args['vendor_type']:
        args['vendor_type'] = 'any'
    order_note = args["order_note"].replace("\r", "")
    order_note = order_note.replace("\n", " ")
    order_note = order_note.replace("  ", " ")
    args['order_note'] = order_note
    mobile_number = format_mobile(args["mobile_number"])
    result = send_whatsapp_msg(args, mobile_number, name)
    if result["result"] in ["success", "PENDING", "SENT", True]:
        new_wt = wtmessages(order_id=args["order_id"], template_name=result["template_name"], broadcast_name=result[
                            "broadcast_name"], status="success", time_sent=datetime.utcnow())
    else:
        new_wt = wtmessages(order_id=args["order_id"], template_name=result["template_name"], broadcast_name=result[
                            "broadcast_name"], status="failed", time_sent=datetime.utcnow())
    db.session.add(new_wt)
    db.session.commit()
    result['order_id'] = str(args['order_id'])
    return result
    r_s_msg["order_id"] = args['order_id']
    return r_s_msg



@app.route('/send_whatsapp_msg_with_s', methods=['GET'])
def send_whatsapp_msg_with_s():
    args = request.args.to_dict(flat=True)
    return send_whatsapp_temp_sess(args)

@app.route("/send_whatsapp_messages/<string:name>", methods=['POST'])
def send_whatsapp_messages_m(name):
    data = request.form.to_dict(flat=False)
    results = []
    feedback_list = {}
    orders = list_orders_with_status(wcapi, {"include": get_list_to_string(data['order_ids[]'])})
    for o in orders:
        wallet_payment = 0
        refunds = 0
        for r in o["refunds"]:
            refunds = refunds + float(r["total"])
        o["total_refunds"] = refunds*-1
        o["total"] = float(o["total"])
        vendor, manager, delivery_date, order_note,  = get_meta_data(o)
        if len(o["fee_lines"]) > 0:
            for item in o["fee_lines"]:
                if "wallet" in item["name"].lower():
                    wallet_payment = (-1)*float(item["total"])
        if vendor in vendor_type.keys():
            o["vendor_type"] = vendor_type[vendor]
        else:
            if vendor == "":
                r = {'result': "Vendor Error", 'order_id': o['id']}
                r['customer_name'] = o['billing']['first_name']+" "+o['billing']['last_name']
                results.append(r)
                continue
            else:
                o["vendor_type"] = ""
        o["wallet_payment"] = wallet_payment
        o["total"] = float(o["total"]) + float(o["wallet_payment"])
        # Template Name
        if name == 'today':
            td = "today_prepay"
            if o["date_paid"] == None:
                td = 'today_postpay'
            params = {'c_name': o['billing']['first_name'], 
            'manager': manager, 'order_id': o['id'], 'order_note': order_note, 'total_amount': o['total'], 'delivery_date': delivery_date, 'payment_method': o['payment_method_title'], 'delivery_charge': o['shipping_total'], 'seller': vendor, 'items_amount': float(o['total'])-float(o['shipping_total']),
                'name': td, 'status': 'tbd-paid, tbd-unpaid', 'vendor_type': o['vendor_type'], 'mobile_number': format_mobile(o['billing']['phone']), 'order_key': o['order_key'], 'url_post_pay': str(o["id"])+"/?pay_for_order=true&key="+str(o["order_key"])}
            r = send_whatsapp_temp_sess(params)
            r['vendor_type'] = o['vendor_type']
            r['button'] = False
            if o['status'] in ['tbd-paid', 'completed'] or (o['status'] == 'processing' and o['payment_method_title'] == 'Pre-paid'):
                r['payment_status'] = "Paid"
            elif o['status'] in ['tbd-unpaid', 'delivered-unpaid'] or (o['status'] == 'processing' and o['payment_method_title'] == 'Pay Online on Delivery'):
                r['button'] = True
                r['payment_status'] = "Unpaid"
                if o['payment_method_title'] != 'Pay Online on Delivery':
                    r['button'] = False
            else:
                r['payment_status'] = ""
        else:
            td = 'feedback_old_prepaid_v2'
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            if len(delivery_date)>0:
                dt = datetime.strptime(delivery_date, '%Y-%m-%d')
                d_date = dt.strftime("%A")+", "+months[dt.month-1]+" " + str(dt.day)
            else:
                d_date = ""
            button = True
            if o['status'] in ['tbd-paid', 'completed'] or (o['status'] == 'processing' and o['payment_method_title'] == 'Pre-paid'):
                p_s = "Paid"
            elif o['status'] in ['tbd-unpaid', 'delivered-unpaid'] or (o['status'] == 'processing' and o['payment_method_title'] == 'Pay Online on Delivery'):
                p_s = "Unpaid"
                if o['payment_method_title'] != 'Pay Online on Delivery':
                    button = False
            else:
                p_s = ""
            params = {'payment_status': p_s,'c_name': o['billing']['first_name'], 
            'manager': manager, 'order_id': o['id'], 'order_note': order_note, 'total_amount': o['total'], 'delivery_date_last_order': d_date, 'payment_method': o['payment_method_title'], 'delivery_charge': o['shipping_total'], 'seller': vendor, 'items_amount': float(o['total'])-float(o['shipping_total']),
                'name': td, 'status': 'tbd-paid, tbd-unpaid', 'vendor_type': o['vendor_type'], 'mobile_number': format_mobile(o['billing']['phone']), 'order_key': o['order_key'], 'url_post_pay': str(o["id"])+"/?pay_for_order=true&key="+str(o["order_key"])}
            r = {'customer_id': o['customer_id'], 'order_id': o['id']}
            if o['customer_id'] in feedback_list:
                o_p = feedback_list[o['customer_id']]
                ids = o_p['vendor_type'].split(" (")[1][:-1]+", #"+str(o['id'])
                vendors = o_p['vendor_type'].split(" (")[0]
                if params['vendor_type'] not in o_p['vendor_type']:
                    vendors = vendors+" + "+params['vendor_type']
                o_p['vendor_type'] = vendors+" ("+ids+")"
                o_p['payment_status'] = o_p['payment_status']+", "+p_s
                if o_p['button'] == True:
                    o_p['button'] = button
                feedback_list[o['customer_id']]=o_p
            else:
                params['vendor_type'] = params['vendor_type']+" (#"+str(o['id'])+")"
                params['button'] = button
                feedback_list[o['customer_id']]=params
        r['customer_name'] = o['billing']['first_name']+" "+o['billing']['last_name']
        r['phone_number'] = format_mobile(o['billing']['phone'])
        results.append(r)
    if name == 'feedback':
        results = []
        for c in feedback_list:
            r = send_whatsapp_temp(feedback_list[c], feedback_list[c]['name'])
            order_ids = feedback_list[c]['order_type'].split(" (")[1][:-1].replace("#", "")
            feedback_list[c]['result'] = r['result']
            feedback_list[c]['customer_name'] = feedback_list[c]['c_name']
            feedback_list[c]['phone_number'] = feedback_list[c]['mobile_number']
            feedback_list[c]['vendor_type'] = feedback_list[c]['order_type']
            feedback_list[c]['order_id'] = order_ids
            results.append(feedback_list[c])
            if feedback_list[c]['button']:
                payment_links = PaymentLinks.query.filter(PaymentLinks.receipt.like("%"+order_ids+"%")).all()
                if len(payment_links)==0:
                    feedback_list[c]['button'] = False
    else:
        today_list = {}
        for r in results:
            if r['phone_number'] not in today_list:
                r['vendor_type'] = r['vendor_type']+" (#"+str(r['order_id'])+")"
                r['order_id'] = str(r['order_id'])
                today_list[r['phone_number']]=r
            else:
                t_d = today_list[r['phone_number']]
                t_d['order_id']+=(", "+str(r['order_id']))
                t_d['result'] = str(t_d['result'])
                t_d['result']+=(", "+str(r['result']))
                t_d['payment_status']+=(", "+r['payment_status'])
                ids = t_d['vendor_type'].split(" (")[1][:-1]+", #"+str(o['id'])
                vendors = t_d['vendor_type'].split(" (")[0]
                if r['vendor_type'] not in t_d['vendor_type']:
                    vendors = vendors+" + "+r['vendor_type']
                t_d['vendor_type'] = vendors+" ("+ids+")"
        results = list(today_list.values())
    return {'result': 'success', 'results': results}

def update_order_status_with_id(order, status, r):
    s = ""
    m = ""
    if status == 'cancel' or status == 'cancel_r':
        s = 'cancelled'
        m = ("Mark as cancelled")
    elif status == 'delivered':
        if order['status'] == 'tbd-unpaid':
            s = 'delivered-unpaid'
            m = ("Mark as delivered-unpaid")
        elif order['status'] == 'tbd-paid':
            s = 'completed'
            m = ("Mark as delivered-paid")
        else:
            if order['date_paid'] == None:
                s = 'delivered-unpaid'
                m = ("Mark as delivered-unpaid")
            else:
                s = 'completed'
                m = ("Mark as delivered-paid")
    elif status == 'tbd':
        if order['status'] == 'pending':
            s = 'tbd-unpaid'
            m = ("Mark as tbd-unpaid")
        elif order['payment_method_title'] not in ['Pre-paid', 'Wallet payment']:
            s = 'tbd-unpaid'
            m = ("Mark as tbd-unpaid") 
        else:
            s = 'tbd-paid'
            m = ("Mark as tbd-paid")
    if r == 'status':
        return s
    else:
        return m

        


@app.route("/change_order_status", methods=['POST'])
def change_order_status():
    data = request.form.to_dict(flat=False)
    result_list = []
    if data['status'][0] == 'cancel':
        msg_text = '*These orders are marked as cancelled*\n\n'
    if data['status'][0] == 'tbd':
        msg_text = '*These orders are marked as to-be-delivered*\n\n'
    if data['status'][0] == 'delivered':
        msg_text = '*These orders are marked as Delivered*\n\n'
    if data['status'][0] == 'cancel_r':
        msg_text = '*These orders are marked as cancelled*\n\n'
    error_text = ""
    success_text = ""
    orders = list_orders_with_status(wcapi, {'include': get_list_to_string(data['order_ids[]'])})
    update_list = []
    wallet_refund = []
    for order in orders:
        order['status'] = update_order_status_with_id(order, data['status'][0], 'status')
        update_list.append({'id': order['id'], 'status': order['status']})
    updates = wcapi_write.post("orders/batch", {"update": update_list}).json()
    for o in updates['update']:
        name = o['billing']['first_name']+" "+o['billing']['last_name']
        message = update_order_status_with_id(o, data['status'][0], 'message')
        wallet_payment = 0
        if len(o["fee_lines"]) > 0:
            for item in oct(i)["fee_lines"]:
                if "wallet" in item["name"].lower():
                    wallet_payment = (-1)*float(item["total"])
        o['total']= float(o['total'])+wallet_payment
        refund_s = "NO"
        if 'error' in o:
            error_text+=str(o['id'])+"-"+name+"-"+message+"\n"
            status = "Failed"
        else:
            status = "Success"
            success_text+=str(o['id'])+"-"+name+"-"+message+"\n"
            if o['payment_method'] == 'wallet' and o['created_via'] == 'subscription' and data['status'][0] == 'cancel_r':
                refund = wcapiw.post("wallet/"+str(o['customer_id']), data={'type': 'credit', 'amount': float(o['total']), 'details': 'Refund added for order ID-'+str(o['id'])}).json()
                if refund['response'] == 'success' and refund['id'] != False:
                    refund_s = "YES"
        result_list.append({'order_id': o['id'], 'status': status, 'message': message, 'name': name,'refund': refund_s})
    msg_text+=success_text
    if len(error_text)>0:
        msg_text+='\n*These orders gave error*\n\n'
        msg_text+=error_text
    response =send_slack_message(client, "VENDOR_WISE", msg_text)
    return {'result': 'success', 'result_list': result_list}

@app.route("/get_copy_messages/<string:id>")
def get_copy_messages(id):
    o = wcapi.get("orders/"+id[6:]).json()
    product_list = list_product_list_form_orders([o], wcapi)
    order_refunds = []
    if len(o["refunds"]) > 0:
        order_refunds = wcapi.get("orders/"+str(o["id"])+"/refunds").json()
    msg = ""
    if 'c_msg' in id:
        delivery_date = ""
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        vendor, manager, delivery_date, order_note,  = get_meta_data(o)
        if delivery_date:
            try:
                dt = datetime.strptime(delivery_date, '%Y-%m-%d')
                delivery_date = months[dt.month-1]+" " + str(dt.day)
            except Exception as e:
                delivery_date=""
        msg = "Here are the order details:\n\n" + "Order ID: " + str(o["id"]) + "\nDelivery Date: " + delivery_date + "\n\n" + \
            list_order_items(o["line_items"], order_refunds, wcapi, product_list) + \
            "*Total Amount: " + \
            get_totals(o["total"], order_refunds) + \
            get_shipping_total(o)+"*\n\n"
        msg = msg + \
            list_order_refunds(order_refunds, o['line_items']) + \
            list_only_refunds(order_refunds)
    else:
        payment_status = "Paid To LeapClub."
        if o['payment_method'] == 'other':
            payment_status = "Cash On Delivery"
        msg = ("Order ID: "+str(o["id"])
                 + "\n\nName: "+o["billing"]["first_name"] +
                 " "+o["billing"]["last_name"]
                 + "\nMobile: "+format_mobile(o["billing"]["phone"])
                 + "\nAddress: "+o["shipping"]["address_1"] + ", "+o["shipping"]["address_2"]+", "+o["shipping"]["city"]+", "+o["shipping"]["state"]+", "+o["shipping"]["postcode"] +
                 ", "+o["billing"]["address_2"]
                     + "\n\nTotal Amount: " +
                 get_totals(o["total"], order_refunds)
                     + get_shipping_total(o)
                     + "\n\n"+list_order_items(o["line_items"], order_refunds, wcapi, product_list)
                     + "Payment Status: "+payment_status
                     + "\nCustomer Note: "+o["customer_note"])
    return {'status': 'success', 'text': msg.strip()}

@app.route("/genSubscriptionLink/<string:id>/<int:amount>")
def genSubscriptionLink(id, amount):
    order = wcapi.get("orders/"+id).json()
    mobile_number = order['billing']["phone"].strip(" ")
    mobile_number = mobile_number[-10:]
    mobile_number = ("91"+mobile_number) if len(mobile_number) == 10 else mobile_number
    reciept = "Wallet-" + str(order['customer_id'])
    payment_links = PaymentLinks.query.filter_by(receipt=reciept).all()
    if len(payment_links) > 0:
        counter = 1
        while True:
            reciept = "Wallet-" + str(order['customer_id'])+"-"+str(counter)
            payment_links = PaymentLinks.query.filter_by(receipt=reciept).all()
            if len(payment_links) == 0:
                break
            counter += 1
    data = {
            "amount": amount*100,
            "receipt": reciept,
            "customer": {
                "name": order["shipping"]["first_name"] + " " + order["shipping"]["last_name"],
                "contact": mobile_number
            },
            "type": "link",
            "view_less": 1,
            "currency": "INR",
            "description": "Thank you for making a healthy and sustainable choice",
            "reminder_enable": False,
            "callback_url": "https://leapclub.in/",
            "callback_method": "get",
            "sms_notify": False,
            'email_notify': False
        }
    try:
        invoice = razorpay_client.invoice.create(data=data)
        status = "success"
        short_url = invoice['short_url']
        new_payment_link = PaymentLinks(order_id=order["id"], receipt=data["receipt"], payment_link_url=invoice['short_url'], contact=format_mobile(order["billing"]["phone"]), name=data["customer"]['name'], created_at=invoice["created_at"], amount=data['amount'], status=status)
    except Exception as e:
        status = "failed"
        short_url = ""
        new_payment_link = PaymentLinks(order_id=order["id"], receipt=data["receipt"], payment_link_url="", contact=order["billing"]
                                        ["phone"], name=data["customer"]['name'], created_at="", amount=data['amount'], status=status)
    db.session.add(new_payment_link)
    db.session.commit()
    data['id'] = order['id']
    data['short_url'] = short_url
    return {'result': 'success', 'data': data}

@app.route("/genMulSubscriptionLink", methods=['POST'])
def genMulSubscriptionLink():
    data = request.form.to_dict(flat=False)
    data['order_ids'] = data['order_ids[]']
    params = get_params(data)
    params["include"] = get_list_to_string(data["order_ids"])
    del params['status']
    orders = wcapi.get("orders", params=params).json()
    customers = {}
    results = []
    for o in orders:
        customer_id = o['customer_id']
        if customer_id in customers:
            customers[customer_id].append(o)
        else:
            customers[customer_id] = [o]
    for customer in customers:
        o_ids = list(map(lambda o: str(o['id']), customers[customer]))
        reciept = "Wallet-" + str(customer)
        payment_links = PaymentLinks.query.filter_by(receipt=reciept).all()
        if len(payment_links) > 0:
            counter = 1
            while True:
                reciept = "Wallet-" + str(customer)+"-"+str(counter)
                payment_links = PaymentLinks.query.filter_by(receipt=reciept).all()
                if len(payment_links) == 0:
                    break
                counter += 1
        total_amount = 0
        for o in customers[customer]:
            wallet_payment = 0
            if len(o["fee_lines"]) > 0:
                for item in o["fee_lines"]:
                    if "wallet" in item["name"].lower():
                        wallet_payment = (-1)*float(item["total"])
            total_amount += (float(get_total_from_line_items(o["line_items"]))+float(
                o["shipping_total"])-wallet_payment-float(get_total_from_line_items(o["refunds"])*-1))
            mobile_number = format_mobile(o['billing']["phone"])
        data1 = {
            "amount": total_amount*100,
            "receipt": reciept,
            "customer": {
                "name": o["shipping"]["first_name"] + " " + o["shipping"]["last_name"],
                "contact": mobile_number
            },
            "type": "link",
            "view_less": 1,
            "currency": "INR",
            "description": "Thank you for making a healthy and sustainable choice",
            "reminder_enable": False,
            "callback_url": "https://leapclub.in/",
            "callback_method": "get",
            "sms_notify": False,
            'email_notify': False
        }
        try:
            invoice = razorpay_client.invoice.create(data=data1)
            status = "success"
            short_url = invoice['short_url']
            for i in o_ids:
                new_payment_link = PaymentLinks(order_id=i, receipt=data1["receipt"], payment_link_url=invoice['short_url'], contact=customer, name=data1["customer"]['name'], created_at=invoice["created_at"], amount=data1['amount'], status=status)
                db.session.add(new_payment_link)
                db.session.commit()
            results.append({"result": "success", 'order_ids': o_ids, 'short_url': invoice['short_url'], 'amount': data1['amount'], 'receipt': reciept, "mobile":customer})
        except Exception as e:
            results.append({"result": "error", 'mobile': customer, 'receipt':reciept, 'amount': data1['amount']})
    return {'results': results}

@app.route("/copy_linked_orders", methods=['POST'])
def copy_linked_orders():
    data = request.form.to_dict(flat=False)
    data['order_ids'] = data['order_ids[]']
    params = get_params(data)
    params["include"] = get_list_to_string(data["order_ids"])
    del params['status']
    orders = wcapi.get("orders", params=params).json()
    customers = {}
    for o in orders:
        if o['customer_id'] in customers:
            customers[o['customer_id']]['ids'].append(str(o['id']))
        else:
            customers[o['customer_id']] = {'ids': [str(o['id'])], 'name': o['billing']['first_name']}
    text = "Linked Orders:\n\n"
    for c in customers:
        ids = " + ".join(customers[c]['ids'])
        ids+=" ("+customers[c]['name']+")\n"
        text+=ids
    return {'status': 'success', 'text': text}

@app.route("/send_payment_link_wt/<string:id>", methods=['POST'])
def send_payment_link_wt(id):
    args = request.form.to_dict(flat=True)
    mobile_number = args['mobile_number']
    payment_link = PaymentLinks.query.filter(PaymentLinks.receipt.like("%"+id+"%")).all()[-1]
    headers = {
        'Authorization': app.config["WATI_AUTHORIZATION"],
        'Content-Type': 'application/json',
    }
    url = app.config["WATI_URL"]+"/api/v1/sendSessionMessage/" + \
        mobile_number + "?messageText="+payment_link.payment_link_url
    response = requests.request(
        "POST", url, headers=headers)
    url = app.config["WATI_URL"]+"/api/v1/sendSessionMessage/" + \
        mobile_number + "?messageText=^ Please pay through this link."
    response = requests.request(
        "POST", url, headers=headers)
    result = json.loads(response.text.encode('utf8'))
    result["template_name"] = 'payment_link_6'
    if result["result"] in ["success", "PENDING", "SENT", True]:
        return result

    # Template Message....
    args_p = {'order_type': args['order_type'], 'razorpay_link': payment_link.payment_link_url}
    url = app.config["WATI_URL"]+"/api/v1/sendTemplateMessage/" + mobile_number
    template_name = 'payment_link_6'
    parameters_s = "["
    for d in args_p:
        parameters_s = parameters_s + \
            '{"name":"'+str(d)+'", "value":"'+str(args_p[d])+'"},'
    parameters_s = parameters_s[:-1]
    parameters_s = parameters_s+"]"
    payload = {
        "template_name": template_name,
        "broadcast_name": "send_payment_link",
        "parameters": parameters_s
    }
    headers = {
        'Authorization': app.config["WATI_AUTHORIZATION"],
        'Content-Type': 'application/json',
    }

    response = requests.request(
        "POST", url, headers=headers, data=json.dumps(payload))

    result = json.loads(response.text.encode('utf8'))
    result["template_name"] = template_name
    return result

@app.route("/wallet")
def wallet():
    m_time = time.time()
    args = request.args.to_dict(flat=True)
    page = 1 if 'page' not in args else int(args['page'])
    include = '' if 'include' not in args else args['include']
    search = '' if 'name' not in args else args['name']
    c_time = time.time()
    customers = wcapi.get("customers", params={'page': page, 'per_page': 25, 'orderby': "id", 'role': 'all', 'include': include, 'search': search}).json()
    print("Time to fetch customers: ", time.time()-c_time)
    c_time = time.time()
    # customers = list_customers_with_wallet_balance(customers, wcapiw)
    print("Time to fetch wallet balance: ", time.time()-c_time)
    print("Total time: ", time.time()-m_time)
    return render_template('wallet/index.html', page=page, customers=customers, format_mobile = format_mobile, query=args)


if __name__ == "__main__":
    db.create_all()
    app.run(debug=True)
