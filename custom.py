import os
import csv
import time
import datetime
import concurrent.futures
from customselectlist import list_created_via
from pytz import timezone
from modules.universal import format_mobile, list_product_list_form_orders


def format_delivery_date(d):
    d_s = d.split("/")
    f_s = d_s[0]+" "
    f_s = f_s+d_s[1]
    f_s = f_s+", "
    f_s = f_s+d_s[2]
    return f_s


def filter_orders(orders, params):
    if len(params) <= 4:
        return orders
    f_orders = []
    for o in orders:
        c = {"payment_status": False, "manager": False}
        if 'status' in params and 'payment_status' in params:
            if params['status'][0] == 'tbd-paid, tbd-unpaid' and params['payment_status'][0] != "":
                params['payment_status'][0] = ""
        if "payment_status" in params:
            if params["payment_status"][0] != "":
                if params["payment_status"][0] == "unpaid":
                    if o["payment_method_title"] == "Pay Online on Delivery":
                        c["payment_status"] = True
                else:
                    if o["payment_method_title"] == 'Pre-paid':
                        c["payment_status"] = True
            else:
                c["payment_status"] = True
        manager = ""
        for item in o["meta_data"]:
            if item["key"] == "_wc_acof_3":
                manager = item["value"]
        if "manager" in params:
            if params["manager"][0] != "":
                if manager in params["manager"]:
                    c["manager"] = True
            else:
                c["manager"] = True
        else:
            c["manager"] = True
        if c["payment_status"] and c["manager"]:
            f_orders.append(o)
    return f_orders


def list_order_items_without_refunds(order_items):
    msg = ""
    for order_item in order_items:
        msg = (
            msg
            + order_item["name"]
            + " x "
            + str(order_item["quantity"])
            + "\n"
            + "₹"
            + str(order_item["price"])
            + " x "
            + str(order_item["quantity"])
            + " = "
            + str(order_item["subtotal"])
            + "\n\n"
        )
    return msg


def list_order_refunds(order_refunds, line_item):
    msg = ""
    line_items = []
    m_list = []
    for r in order_refunds:
        for ri in r["line_items"]:
            if ri["meta_data"][0]["value"] in m_list:
                for l in line_items:
                    if l["meta_data"][0]["value"] == ri["meta_data"][0]["value"]:
                        l["quantity"] = l["quantity"] + ri["quantity"]
            else:
                line_items.append(ri)
                m_list.append(ri["meta_data"][0]["value"])
    for order_item in line_items:
        item_id = list(filter(lambda x: x['key'] == '_refunded_item_id', order_item['meta_data']))[0]['value']
        o_i = list(filter(lambda oi: int(oi["id"]) == int(item_id), line_item))
        if int(o_i[0]['quantity']) == 0:
            msg = (
                msg
                + order_item["name"]
                + " x "
                + str(order_item["quantity"]*-1)
                + "\n"
                + "₹"
                + str(order_item["price"])
                + " x "
                + str(order_item["quantity"]*-1)
                + " = "
                + str(order_item["subtotal"])[1:]
                + "\n\n"
            )
    if len(msg) > 0:
        msg = "We are not able to send: \n\n"+msg
    return msg

def get_line_items_with_product(order_items, wcapi):
    def get_product(item):
        product = wcapi.get("products/"+str(item['product_id'])).json()
        item['product'] = product
        return item
    with concurrent.futures.ThreadPoolExecutor() as executor:
        result = executor.map(get_product, order_items)
    return list(result)

def list_order_items(order_items, refunds, wcapi, product_list):
    msg = ""
    total_refunds = []
    for r in refunds:
        for ri in r["line_items"]:
            total_refunds.append(ri)
    for order_item in order_items:
        order_item['product'] = product_list[order_item['product_id']]
        for refund in total_refunds:
            if order_item["id"] == int(refund["meta_data"][0]["value"]):
                order_item["quantity"] = order_item["quantity"] + \
                    refund["quantity"]
                order_item["total"] = float(
                    order_item["total"]) + float(refund["total"])
        if order_item["quantity"] > 0:
            name_w = order_item['name'].split("(")
            if order_item['product']['weight'] != "" and len(name_w) == 2:
                name_w_g = name_w[1].split(" ")
                f_q = float(order_item['product']['weight'])*float(order_item['quantity'])
                if f_q<1:
                    f_q = f_q*1000
                    f_q = int(f_q) if float(int(f_q))==f_q else round(f_q, 2)
                    name_w = name_w[0]+"("+str(f_q)+" gm)"
                else:
                    f_q = int(f_q) if float(int(f_q))==f_q else round(f_q, 2)
                    name_w = name_w[0]+"("+str(f_q)+" kg)"
                msg = (
                    msg
                    + name_w
                    + "\n₹"
                    + str(round(order_item["price"],1))
                    + " x "
                    + str(order_item["quantity"])
                    + " = "
                    + str(round(float(order_item["total"]),1))
                    + "\n\n"
                )

            else:
                msg = (
                    msg
                    + order_item["name"]
                    + " x "
                    + str(order_item["quantity"])
                    + "\n₹"
                    + str(round(order_item["price"], 1))
                    + " x "
                    + str(order_item["quantity"])
                    + " = "
                    + str(round(float(order_item["total"]),1))
                    + "\n\n"
                )
    return msg


def list_order_items_csv(order_items, refunds, wcapi, product_list):
    msg = ""
    total_refunds = []
    for r in refunds:
        for ri in r["line_items"]:
            total_refunds.append(ri)
    for order_item in order_items:
        order_item['product'] = product_list[str(order_item['product_id'])]
        for refund in total_refunds:
            if order_item["id"] == int(refund["meta_data"][0]["value"]):
                order_item["quantity"] = order_item["quantity"] + \
                    refund["quantity"]
                order_item["total"] = float(
                    order_item["total"]) + float(refund["total"])
        if order_item["quantity"] > 0:
            name_w = order_item['name'].split("(")
            if order_item['product']['weight'] != "" and len(name_w) == 2:
                name_w_g = name_w[1].split(" ")
                f_q = float(order_item['product']['weight'])*float(order_item['quantity'])
                if f_q<1:
                    f_q = f_q*1000
                    f_q = int(f_q) if float(int(f_q))==f_q else round(f_q, 2)
                    name_w = name_w[0]+"("+str(f_q)+" gm)"
                else:
                    f_q = int(f_q) if float(int(f_q))==f_q else round(f_q, 2)
                    name_w = name_w[0]+"("+str(f_q)+" kg)"
                msg = (
                    msg
                    + name_w
                    + " = "
                    + str(order_item["total"])
                    + "\n\n"
                )
            else:
                msg = (
                msg
                + order_item["name"]
                + " x "
                + str(order_item["quantity"])
                + " = "
                + str(order_item["total"])
                + "\n\n"
            )
    return msg


def list_only_refunds(order_refunds):
    msg = ""
    for r in order_refunds:
        if len(r["line_items"]) == 0:
            msg = msg+r["reason"]+": "+r["amount"]+"\n\n"
    return msg


def get_totals(total, refunds):
    msg = str(total)
    for r in refunds:
        msg = msg+" - " + str(r["amount"])
        total = float(total) - float(r["amount"])
    if len(refunds) > 0:
        msg = msg+" = "+str(total)
    return str(total)


def get_list_to_string(l):
    list_s = ""
    for i in l:
        list_s += i
        list_s += ", "
    list_s = list_s[:-2]
    return list_s


def get_params(args):
    params = {"per_page": 50}
    if "page" in args:
        params["page"] = int(args["page"][0])
    else:
        params["page"] = 1
    if "status" in args:
        if 'status_f' in args:
            params['status'] = get_list_to_string(args['status_f'])
        elif args["status"][0] == 'subscription':
            params["status"] = "any"
            params["created_via"] = "subscription"
        elif args['status'][0] == "dairy":
            params["status"] = "processing, tbd-unpaid, tbd-paid"
            params['vendor'] = 'mrdairy, Mr. Dairy'
            params['created_via'] = 'admin, checkout, Order clone'
        else:
            if args["status"][0] == "tbd-paid, tbd-unpaid":
                l_c = list_created_via.copy()
                l_c.remove("subscription")
                params["created_via"] = get_list_to_string(l_c)
            if 'payment_status' in args and args["status"][0] == "tbd-paid, tbd-unpaid":
                    if args['payment_status'][0] == 'paid':
                        params['status'] = 'tbd-paid'
                    elif args['payment_status'][0] == 'unpaid':
                        params['status'] = 'tbd-unpaid'
                    else:
                        params['status'] = 'tbd-paid, tbd-unpaid'
            else:
                params["status"] = args["status"][0]
    else:
        l_c = list_created_via.copy()
        l_c.remove("subscription")
        params["created_via"] = get_list_to_string(l_c)
        params["status"] = "tbd-paid, tbd-unpaid"
    if "order_ids" in args:
        if args["order_ids"][0] != "":
            params["include"] = args["order_ids"][0]
    if "name" in args:
        if args["name"][0] != "":
            params["search"] = args["name"][0]
    if "phone_number" in args:
        if args["phone_number"][0] != "":
            params["search"] = args["phone_number"][0]
    if "created_via" in args:
        if args['created_via'][0] != "":
            params["created_via"] = get_list_to_string(args["created_via"])
    if "vendor" in args:
        if args["vendor"][0] != "":
            params["vendor"] = get_list_to_string(args["vendor"])
    if "delivery_date" in args:
        if args["delivery_date"][0] != "":
            params["delivery_date"] = args["delivery_date"][0].replace(
                "/", "-")
    if "after" in args:
        if args["after"][0] != "":
            params["after"] = args["after"][0].replace("/", "-")+"T00:00:00"
    if "before" in args:
        if args["before"][0] != "":
            params["before"] = args["before"][0].replace("/", "-")+"T00:00:00"
    return params


def get_shipping_total(o):
    if float(o["shipping_total"]) > 0:
        return " (Including delivery charge of Rs "+o["shipping_total"]+")"
    else:
        return ""


def get_shipping_total_for_csv(o):
    if float(o["shipping_total"]) > 0:
        return " (Including Rs "+o["shipping_total"]+" delivery charge)"
    else:
        return ""


def get_orders_with_messages(orders, wcapi):
    product_list = list_product_list_form_orders(orders, wcapi)
    def _get_orders_with_messages(o):
        delivery_date = ""
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for item in o["meta_data"]:
            if item["key"] == "_delivery_date":
                if delivery_date == "":
                    delivery_date = item["value"]
            elif item["key"] == "_wc_acof_2_formatted":
                if delivery_date == "":
                    delivery_date = item["value"]
        if delivery_date:
            try:
                dt = datetime.datetime.strptime(delivery_date, '%Y-%m-%d')
                delivery_date = months[dt.month-1]+" " + str(dt.day)
            except:
                delivery_date=""
        order_refunds = []
        if len(o["refunds"]) > 0:
            order_refunds = wcapi.get("orders/"+str(o["id"])+"/refunds").json()
        c_msg = "Here are the order details:\n\n" + "Order ID: " + str(o["id"]) + "\nDelivery Date: " + delivery_date + "\n\n" + \
            list_order_items(o["line_items"], order_refunds, wcapi, product_list) + \
            "*Total Amount: " + \
            get_totals(o["total"], order_refunds) + \
            get_shipping_total(o)+"*\n\n"
        c_msg = c_msg + \
            list_order_refunds(order_refunds, o['line_items']) + \
            list_only_refunds(order_refunds)
        payment_status = "Paid To LeapClub."
        if o['payment_method'] == 'other':
            payment_status = "Cash On Delivery"
        s_msg = ("Order ID: "+str(o["id"])
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
        o["c_msg"] = c_msg
        o["s_msg"] = s_msg
        return o
    with concurrent.futures.ThreadPoolExecutor() as executor:
        result = executor.map(_get_orders_with_messages, orders)
    return list(result)


def get_orders_with_messages_without(orders, wcapi):
    product_list = list_product_list_form_orders(orders, wcapi)
    def _get_orders_with_messages(o):
        delivery_date = ""
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for item in o["meta_data"]:
            if item["key"] == "_delivery_date":
                if delivery_date == "":
                    delivery_date = item["value"]
            elif item["key"] == "_wc_acof_2_formatted":
                if delivery_date == "":
                    delivery_date = item["value"]
        if delivery_date:
            dt = datetime.datetime.strptime(delivery_date, '%Y-%m-%d')
            delivery_date = months[dt.month-1]+" " + str(dt.day)
        order_refunds = []
        if len(o["refunds"]) > 0:
            order_refunds = wcapi.get("orders/"+str(o["id"])+"/refunds").json()
        c_msg = "Order ID: " + str(o["id"]) + "\nDelivery Date: " + delivery_date + "\n\n" + \
            list_order_items(o["line_items"], order_refunds, wcapi, product_list) + \
            "*Total Amount: " + \
            get_totals(o["total"], order_refunds) + \
            get_shipping_total(o)+"*\n\n"
        c_msg = c_msg + \
            list_order_refunds(order_refunds, o['line_items']) + \
            list_only_refunds(order_refunds)
        o["c_msg"] = c_msg
        o['total_amount'] = get_totals(o["total"], order_refunds)
        return o
    with concurrent.futures.ThreadPoolExecutor() as executor:
        result = executor.map(_get_orders_with_messages, orders)
    return list(result)


def get_orders_with_wallet_balance(orders, wcapiw):
    def _get_orders_with_wallet_balance(o):
        balance = wcapiw.get("current_balance/"+str(o["customer_id"]))
        o["wallet_balance"] = float(balance.text[1:-1])
        return o
    with concurrent.futures.ThreadPoolExecutor() as executor:
        result = executor.map(_get_orders_with_wallet_balance, orders)
    return list(result)


def get_csv_from_orders(orders, wcapi):
    f = open("sample.csv", "w+")
    writer = csv.DictWriter(
        f, fieldnames=["Order ID", "Customer Detail", "Total Amount", "Order Details", "Comments", "Customer Note"])
    writer.writeheader()
    for o in orders:
        wallet_payment = 0
        if len(o["fee_lines"]) > 0:
            for item in o["fee_lines"]:
                if item["name"] == "Via wallet":
                    wallet_payment = (-1)*float(item["total"])
                    break
        o["total"] = float(o["total"]) + float(wallet_payment)
        refunds = []
        if len(o["refunds"]) > 0:
            refunds = wcapi.get("orders/"+str(o["id"])+"/refunds").json()
        writer.writerow({
            "Order ID": o["id"],
            "Customer Detail": "Name: "+o["billing"]["first_name"]+" "+o["billing"]["last_name"]+"\nMobile: "+format_mobile(o["billing"]["phone"])
            + "\nAddress: "+o["shipping"]["address_1"] + ", "+o["shipping"]["address_2"]+", " +
            o["shipping"]["city"]+", "+o["shipping"]["state"] +
            ", "+o["shipping"]["postcode"],
            "Total Amount": get_totals(o["total"], refunds)+get_shipping_total_for_csv(o),
            "Order Details": list_order_items_csv(o["line_items"], refunds, wcapi),
            "Comments": "Payment Status: Paid To Leap",
            "Customer Note": o["customer_note"]
        })
        writer.writerow({})
    f.close()
    f = open("sample.csv", "r")
    result = f.read()
    os.remove("sample.csv")
    return result


def get_total_from_line_items(items):
    total = 0
    for i in items:
        total += float(i["total"])
    return total


def get_csv_from_vendor_orders(orders, wcapi):
    f = open("sample.csv", "w+")
    writer = csv.DictWriter(
        f, fieldnames=["Date Created", "Delivery Date", "Order ID", "Customer Detail", "Total Order Amount", "Refund Amount", "Delivery Charge", "Order Items", "Payment Method", "Status", "Item Total"])
    writer.writeheader()
    for o in orders:
        delivery_date = ""
        for item in o["meta_data"]:
            if item["key"] == "_delivery_date":
                if delivery_date == "":
                    delivery_date = item["value"]
            elif item["key"] == "_wc_acof_2_formatted":
                if delivery_date == "":
                    delivery_date = item["value"]
        wallet_payment = 0
        if len(o["fee_lines"]) > 0:
            for item in o["fee_lines"]:
                if item["name"] == "Via wallet":
                    wallet_payment = (-1)*float(item["total"])
                    break
        o["total"] = float(o["total"]) + float(wallet_payment)
        refunds = []
        if len(o["refunds"]) > 0:
            refunds = wcapi.get("orders/"+str(o["id"])+"/refunds").json()
        writer.writerow({
            "Date Created": o["date_created"],
            "Delivery Date": delivery_date,
            "Order ID": o["id"],
            "Customer Detail":  "Name: "+o["billing"]["first_name"]+" "+o["billing"]["last_name"]+"\nMobile: "+format_mobile(o["billing"]["phone"])
            + "\nAddress: "+o["shipping"]["address_1"] + ", "+o["shipping"]["address_2"]+", " +
            o["shipping"]["city"]+", "+o["shipping"]["state"] +
            ", "+o["shipping"]["postcode"],
            "Total Order Amount": o["total"],
            "Refund Amount": get_total_from_line_items(o["refunds"])*-1,
            "Delivery Charge": o["shipping_total"],
            "Order Items": list_order_items_csv(o["line_items"], refunds, wcapi)+list_order_refunds(refunds, o['line_items']),
            "Payment Method": o["payment_method_title"],
            "Status": o["status"],
            "Item Total": get_total_from_line_items(o["line_items"])
        })
        writer.writerow({})
    f.close()
    f = open("sample.csv", "r")
    result = f.read()
    os.remove("sample.csv")
    return result


def get_checkout_url(o):
    url = "https://leapclub.in/checkout/order-pay/" + \
        str(o["id"])+"/?pay_for_order=true&key="+o["order_key"]
    return url


def list_categories_with_products(products):
    main_list = {}
    d_c = []
    for p in products:
        if len(p["categories"]) > 1:
            d_c.append(p)
        for c in p["categories"]:
            if c["name"] in main_list.keys():
                main_list[c["name"]].append(p)
            else:
                main_list[c["name"]] = []
    txt = ""
    for c in main_list:
        if len(main_list[c]) > 0:
            txt = txt+"\n*"+c+"*\n\n"
            for p in main_list[c]:
                txt = txt+p["name"]+" - ₹"+p["price"]+"\n"
    return(txt)


def list_categories(wcapi):
    args = {"per_page": 100}
    categories = []
    page = 1
    while True:
        args["page"] = page
        c = wcapi.get("products/categories", params=args).json()
        categories.extend(c)
        page = page+1
        if len(c) < 100:
            break
    return categories


def list_all_orders_tbd(wcapi):
    orders = []
    page = 1
    while True:
        order = wcapi.get("orders", params={
                          "page": page, "per_page": 100, "status": "tbd-paid, tbd-unpaid"}).json()
        orders.extend(order)
        page = page+1
        if len(order) < 100:
            break
    total = []
    for o in orders:
        if o["created_via"] == "subscription":
            total.append(o)
    return total


def list_created_via_with_filter(orders):
    created_vias = []
    for o in orders:
        if o["created_via"] not in created_vias:
            created_vias.append(o["created_via"])
    return created_vias


def filter_orders_with_subscription(orders, args):
    new_list = []
    if "status" in args:
        if args["status"][0] == "subscription":
            for o in orders:
                if o["created_via"] == "subscription":
                    new_list.append(o)
        elif args["status"][0] == "tbd-paid, tbd-unpaid":
            for o in orders:
                if o["created_via"] != "subscription":
                    new_list.append(o)
        else:
            return orders
    else:
        for o in orders:
            if o["created_via"] != "subscription":
                new_list.append(o)
    return new_list


def list_orders_with_status(wcapi, params):
    def get_order(params):
        order = wcapi.get("order2", params=params)
        return order
    page = 1
    ctime = time.time()
    forder = wcapi.get("order2", params=params)
    total_pages = int(forder.headers["X-WP-TotalPages"])
    p_list = []
    p = 2
    while p < total_pages+1:
        params["page"] = p
        p_list.append(params.copy())
        p += 1
    with concurrent.futures.ThreadPoolExecutor() as executor:
        result = executor.map(get_order, p_list)
    orders = list(result)
    orders.insert(0, forder)
    o_list = []
    for o in orders:
        o_list.extend(o.json())
    return o_list


def list_orders_with_status_N2(wcapi, params):
    def get_order(params):
        order = wcapi.get("orders", params=params)
        return order
    page = 1
    ctime = time.time()
    forder = wcapi.get("orders", params=params)
    total_pages = int(forder.headers["X-WP-TotalPages"])
    p_list = []
    p = 2
    while p < total_pages+1:
        params["page"] = p
        p_list.append(params.copy())
        p += 1
    with concurrent.futures.ThreadPoolExecutor() as executor:
        result = executor.map(get_order, p_list)
    orders = list(result)
    orders.insert(0, forder)
    o_list = []
    for o in orders:
        o_list.extend(o.json())
    return o_list


def update_order_status(order, invoice_id, wcapi):
    order_id = order['id']
    data = {}
    c_date = datetime.datetime.now(timezone('Asia/Kolkata'))
    utc_time = datetime.datetime.utcnow()
    format = '%Y-%m-%dT%H:%M:%S'
    data['payment_method'] = 'cod'
    data['payment_method_title'] = 'Pay Online on Delivery'
    data['transaction_id'] = invoice_id
    data['date_paid'] = c_date.strftime(format)
    data['date_paid_gmt'] = utc_time.strftime(format)
    if order['status'] in ['tbd-unpaid']:
        data['status'] = 'tbd-paid'
        u_order = wcapi.put("orders/"+str(order_id), data).json()
        if 'id' in u_order.keys():
            return True
        else:
            return False
    elif order['status'] in ['delivered-unpaid']:
        data['status'] = 'completed'
        data['date_completed'] = c_date.strftime(format)
        data['date_completed_gmt'] = utc_time.strftime(format)
        u_order = wcapi.put("orders/"+str(order_id), data).json()
        if 'id' in u_order.keys():
            return True
        else:
            return False
    else:
        False
    


def get_products_from_thread(product_ids, wcapi):
    def get_product(id):
        product = wcapi.get("products/"+str(id)).json()
        return product
    with concurrent.futures.ThreadPoolExecutor() as executor:
        result = executor.map(get_product, product_ids)
    return list(result)


def get_csv_from_products(orders, wcapi, format):
    line_items = list(map(lambda x: x['line_items'], orders))
    line_items_o = []
    for o in line_items:
        line_items_o.extend((o))
    product_list = []
    is_include = []
    for p in line_items_o:
        product_id = p['product_id']
        if product_id in is_include:
            for i in product_list:
                if i['Product ID'] == product_id:
                    i['Quantity'] += p['quantity']
                    i['orders'] +=1
        else:
            is_include.append(product_id)
            product_list.append(
                {"Product ID": product_id, "Product Name": p['name'], "Quantity": p['quantity'], 'orders': 1})
    products = get_products_from_thread(is_include, wcapi)
    f = open("sample.csv", "w+")
    writer = csv.DictWriter(
        f, fieldnames=["Product ID", "Product Name", "Quantity", "Weight Existed"])
    writer.writeheader()
    for p in product_list:
        p['Product Name'] = p['Product Name'].replace("amp;", " ")
        weight = list(filter(lambda pi: (pi['id'] == p['Product ID']), products))[
            0]['weight']
        is_weight = "NO"
        total_quantity = p['Quantity']
        if weight != "":
            is_weight = "YES"
            total_quantity = float(p['Quantity'])*float(weight)
            name_w = p['Product Name'].split("(")
            if len(name_w) == 2:
                name_w_g = name_w[1].split(" ")
                f_q=total_quantity
                if f_q<1:
                    f_q = f_q*1000
                    f_q = int(f_q) if float(int(f_q))==f_q else round(f_q, 2)
                else:
                    f_q = int(f_q) if float(int(f_q))==f_q else round(f_q, 2)
                p['Product Name'] = name_w[0]
        p['Weight Existed'] = is_weight
        p['Quantity'] = total_quantity
        writer.writerow({
            "Product ID": p['Product ID'],
            "Product Name": p['Product Name'],
            "Quantity": total_quantity,
            "Weight Existed": is_weight
        })
        writer.writerow({})
    f.close()
    f = open("sample.csv", "r")
    result = f.read()
    os.remove("sample.csv")
    if format == "csv":
        return result
    else:
        return product_list


def get_orders_with_customer_detail(orders):
    for o in orders:
        cnmsg = ""
        if o['payment_method']=='other':
            cnmsg = "\n\nCash on delivery"
        msg = str(o['id'])+" ("+o['billing']['first_name']+")\n"+format_mobile(o['billing']['phone'])+"\n"+o["shipping"]["address_1"] + ", "+o["shipping"]["address_2"] + \
            ", "+o["shipping"]["city"]+", "+o["shipping"]["state"] + ", " + \
            o["shipping"]["postcode"]+"\n\nTotal Amount: " + \
            str(o['total'])+"\n\nCustomer Note: "+o['customer_note']+cnmsg
        o['c_msg'] = msg
    return orders

def get_orders_with_supplier(orders, wcapi):
    product_list = list_product_list_form_orders(orders, wcapi)
    for o in orders:
        if len(o["refunds"]) > 0:
            order_refunds = wcapi.get("orders/"+str(o["id"])+"/refunds").json()
        else:
            order_refunds = []
        payment_status = "Paid To LeapClub."
        if o['payment_method'] == 'other':
            payment_status = "Cash On Delivery"

        s_msg = ("Order ID: "+str(o["id"])
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
        o["s_msg"] = s_msg
    return orders
