from custom import get_totals, list_order_items, list_orders_with_status, list_orders_with_status_N2
from datetime import datetime, timedelta
from slack_chennels import CHANNELS
from modules.universal import format_mobile, send_slack_message, send_slack_message_thread, list_product_list_form_orders


def get_total_from_params(wcapi, params):
    orders = list_orders_with_status_N2(wcapi, params)
    total_o = 0
    for o in orders:
        total_o += float(o['total'])
    return total_o


def send_slack_message_(client, wcapi, o):
    params = {'per_page': 100}
    params['status'] = "processing, tbd-unpaid, tbd-paid, delivered-unpaid, completed"
    params['customer'] = int(o['customer_id'])
    c_date = datetime.today().date().replace(day=1)
    params['after'] = c_date.strftime("%Y-%m-%dT%H:%M:%S")
    total_o = get_total_from_params(wcapi, params)
    params['status'] = "tbd-unpaid,delivered-unpaid"
    del params['after']
    total_unpaid = get_total_from_params(wcapi, params)
    vendor = ""
    delivery_date = ""
    payment_status = "Paid"
    if o["date_paid"] == None:
        payment_status = "Unpaid"
    for item in o["meta_data"]:
        if item["key"] == "wos_vendor_data":
            vendor = item["value"]["vendor_name"]
        elif item["key"] == "_wc_acof_6" and item['value'] != "":
            vendor = item["value"]
        elif item["key"] == "_delivery_date":
            if delivery_date == "":
                delivery_date = item["value"]
        elif item["key"] == "_wc_acof_2_formatted":
            if delivery_date == "":
                delivery_date = item["value"]
    if len(o["refunds"]) > 0:
        order_refunds = wcapi.get("orders/"+str(o["id"])+"/refunds").json()
    else:
        order_refunds = []

    taguser = ""
    if o['created_via'] == "checkout" and vendor == "Mr. Dairy":
        taguser = "\n"+CHANNELS['TAG_USER_ID']
    s_msg = (
        "*Order ID: "+str(o["id"])
        + "*\nName: "+o["billing"]["first_name"] + " " +
        o["billing"]["last_name"] + " | Mobile: "+format_mobile(o["billing"]["phone"])
        + "\nAddress: "+o["shipping"]["address_1"] + ", "+o["shipping"]["address_2"]+", "+o["shipping"]["city"] +
        ", "+o["shipping"]["state"]+", " +
        o["shipping"]["postcode"] + ", "+o["billing"]["address_2"]
        + "\nPayment Status: " +
        payment_status +
        " | Payment Method: "+o["payment_method_title"]
        + "\nDelivery Date: "+delivery_date+" | Vendor: "+vendor
        + "\nTotal Amount: " +
        get_totals(o["total"], order_refunds)
        + " | Delivery Charge: "+o["shipping_total"]
        + "\nStatus: " + o['status']
        + " | Created_via: " + o['created_via']
        + "\nCustomer Notes: " + o["customer_note"]
        + "\nMonthly Total: " + str(total_o)
        + " | Total Unpaid Amount: " + str(total_unpaid)
        + taguser
    )
    product_list = list_product_list_form_orders([o], wcapi)
    th_s_msg = "*Order Items*\n" + \
        list_order_items(o["line_items"], order_refunds, wcapi, product_list)
    response = send_slack_message_thread(client, 'ORDER_NOTIFICATIONS', s_msg, th_s_msg)
    return response


def send_slack_message_dairy(client, wcapi, o):
    params = {'per_page': 100}
    params['status'] = "processing, tbd-unpaid, tbd-paid, delivered-unpaid, completed"
    params['customer'] = int(o['customer_id'])
    c_date = datetime.today().date().replace(day=1)
    params['after'] = c_date.strftime("%Y-%m-%dT%H:%M:%S")
    total_o = get_total_from_params(wcapi, params)
    params['status'] = "tbd-unpaid,delivered-unpaid"
    del params['after']
    total_unpaid = get_total_from_params(wcapi, params)
    vendor = ""
    delivery_date = ""
    payment_status = "Paid"
    if o["date_paid"] == None:
        payment_status = "Unpaid"
    for item in o["meta_data"]:
        if item["key"] == "wos_vendor_data":
            vendor = item["value"]["vendor_name"]
        elif item["key"] == "_wc_acof_6" and item['value'] != "":
            vendor = item["value"]
        elif item["key"] == "_delivery_date":
            if delivery_date == "":
                delivery_date = item["value"]
        elif item["key"] == "_wc_acof_2_formatted":
            if delivery_date == "":
                delivery_date = item["value"]
    if len(o["refunds"]) > 0:
        order_refunds = wcapi.get("orders/"+str(o["id"])+"/refunds").json()
    else:
        order_refunds = []

    taguser = ""
    if o['created_via'] == "checkout" and vendor == "Mr. Dairy":
        taguser = "\n"+CHANNELS['TAG_USER_ID']
    s_msg = (
        "*Order ID: "+str(o["id"])
        + "*\nName: "+o["billing"]["first_name"] + " " +
        o["billing"]["last_name"] + " | Mobile: "+format_mobile(o["billing"]["phone"])
        + "\nAddress: "+o["shipping"]["address_1"] + ", "+o["shipping"]["address_2"]+", "+o["shipping"]["city"] +
        ", "+o["shipping"]["state"]+", " +
        o["shipping"]["postcode"] + ", "+o["billing"]["address_2"]
        + "\nPayment Status: " +
        payment_status +
        " | Payment Method: "+o["payment_method_title"]
        + "\nDelivery Date: "+delivery_date+" | Vendor: "+vendor
        + "\nTotal Amount: " +
        get_totals(o["total"], order_refunds)
        + " | Delivery Charge: "+o["shipping_total"]
        + "\nStatus: " + o['status']
        + " | Created_via: " + o['created_via']
        + "\nCustomer Notes: " + o["customer_note"]
        + "\nMonthly Total: " + str(total_o)
        + " | Total Unpaid Amount: " + str(total_unpaid)
        + taguser
    )
    product_list = list_product_list_form_orders([o], wcapi)
    th_s_msg = "*Order Items*\n" + \
        list_order_items(o["line_items"], order_refunds, wcapi, product_list)
    response = send_slack_message_thread(client, 'DAIRY_NOTIFICATIONS', s_msg, th_s_msg)
    return response


def send_slack_message_calcelled(client, wcapi, o):
    vendor = ""
    delivery_date = ""
    payment_status = "Paid"
    if o["date_paid"] == None:
        payment_status = "Unpaid"
    for item in o["meta_data"]:
        if item["key"] == "wos_vendor_data":
            vendor = item["value"]["vendor_name"]
        elif item["key"] == "_wc_acof_6" and item['value'] != "":
            vendor = item["value"]
        elif item["key"] == "_delivery_date":
            if delivery_date == "":
                delivery_date = item["value"]
        elif item["key"] == "_wc_acof_2_formatted":
            if delivery_date == "":
                delivery_date = item["value"]
    if len(o["refunds"]) > 0:
        order_refunds = wcapi.get("orders/"+str(o["id"])+"/refunds").json()
    else:
        order_refunds = []
    s_msg = (
        "*Order ID: "+str(o["id"])
        + " HAS BEEN CANCELLED*\nName: "+o["billing"]["first_name"] + " " +
        o["billing"]["last_name"] + " | Mobile: "+format_mobile(o["billing"]["phone"])
        + "\nAddress: "+o["shipping"]["address_1"] + ", "+o["shipping"]["address_2"]+", "+o["shipping"]["city"] +
        ", "+o["shipping"]["state"]+", " +
        o["shipping"]["postcode"] + ", "+o["billing"]["address_2"]
        + "\nPayment Status: " +
        payment_status +
        " | Payment Method: "+o["payment_method_title"]
        + "\nDelivery Date: "+delivery_date+" | Vendor: "+vendor
        + "\nTotal Amount: " +
        get_totals(o["total"], order_refunds)
        + " | Delivery Charge: "+o["shipping_total"]

    )
    product_list = list_product_list_form_orders([o], wcapi)
    th_s_msg = "*Order Items*\n" + \
        list_order_items(o["line_items"], order_refunds, wcapi, product_list)
    response = send_slack_message_thread(client, 'ORDER_NOTIFICATIONS', s_msg, th_s_msg)
    return response


def send_slack_message_calcelled_dairy(client, wcapi, o):
    vendor = ""
    delivery_date = ""
    payment_status = "Paid"
    if o["date_paid"] == None:
        payment_status = "Unpaid"
    for item in o["meta_data"]:
        if item["key"] == "wos_vendor_data":
            vendor = item["value"]["vendor_name"]
        elif item["key"] == "_wc_acof_6" and item['value'] != "":
            vendor = item["value"]
        elif item["key"] == "_delivery_date":
            if delivery_date == "":
                delivery_date = item["value"]
        elif item["key"] == "_wc_acof_2_formatted":
            if delivery_date == "":
                delivery_date = item["value"]
    if len(o["refunds"]) > 0:
        order_refunds = wcapi.get("orders/"+str(o["id"])+"/refunds").json()
    else:
        order_refunds = []
    total_r = 0
    for r in order_refunds:
        total_r += float(r['amount'])
    s_msg = (
        "*Order ID: "+str(o["id"])
        + " HAS BEEN CANCELLED*\nName: "+o["billing"]["first_name"] + " " +
        o["billing"]["last_name"] + " | Mobile: "+format_mobile(o["billing"]["phone"])
        + " | Payment Method: "+o["payment_method_title"]
        + "\nDelivery Date: "+delivery_date+" | Vendor: "+vendor
        + "\nTotal Amount: " +
        get_totals(o["total"], order_refunds)
        + " | Delivery Charge: "+o["shipping_total"]
        + "\n*Total Refund: "+str(total_r)+"*"
        + "\nAddress: "+o["shipping"]["address_1"] + ", "+o["shipping"]["address_2"]+", "+o["shipping"]["city"] +
        ", "+o["shipping"]["state"]+", " +
        o["shipping"]["postcode"] + ", "+o["billing"]["address_2"]
        + "\nPayment Status: " +
        payment_status

    )
    product_list = list_product_list_form_orders([o], wcapi)
    th_s_msg = "*Order Items*\n" + \
        list_order_items(o["line_items"], order_refunds, wcapi, product_list)
    response = send_slack_message_thread(client, 'DAIRY_NOTIFICATIONS', s_msg, th_s_msg)
    return response


def send_slack_for_product(client, product, topic):
    categories = ""
    tags = ""
    for c in product['categories']:
        categories += c['name']
        categories += ", "
    for t in product['tags']:
        tags += t['name']
        tags += ", "
    categories = categories[:-2]
    tags = tags[:-2]
    s_msg = (
        "*A product is Added/Updated!*\n"
        + "\n*Product Name:* "+product['name']
        + "\n*Product Categories:* "+categories
        + "\n*Shipping Class:* "+product['shipping_class']
        + "\n*Regular Price:* "+product['regular_price']
        + "\n*Product Tags:* "+tags
        + "\n*Stock Status:* "+product['stock_status']
        + "\n*Vendor:* "
    )
    response =send_slack_message(client, "PRODUCT_NOTIFICATIONS", s_msg)
    return response


def get_new_customers(wcapi, orders):
    customers = list(map(lambda o: o['customer_id'], orders))
    customers = list(set(customers))
    new_customers = []
    for c in customers:
        orders = list_orders_with_status_N2(
            wcapi, {'customer': c, 'per_page': 100, 'status': 'processing, tbd-unpaid, tbd-paid, delivered-unpaid, completed'})
        orders.sort(key=lambda o: datetime.strptime(
            o['date_created'], "%Y-%m-%dT%H:%M:%S"), reverse=False)
        o = orders[0]
        delivery_date = ""
        for item in o["meta_data"]:
            if item["key"] == "_delivery_date":
                if delivery_date == "":
                    delivery_date = item["value"]
            elif item["key"] == "_wc_acof_2_formatted":
                if delivery_date == "":
                    delivery_date = item["value"]
        if delivery_date == str(datetime.now().date()):
            new_customers.append(c)
    return new_customers


def send_slack_for_vendor_wise(client, wcapi):
    params = {"per_page": 100}
    params["status"] = 'tbd-unpaid, tbd-paid'
    params["delivery_date"] = str(datetime.now().date())
    params['created_via'] = 'checkout, admin, Order clone'
    orders = list_orders_with_status(wcapi, params)
    del params['delivery_date']
    params['created_via'] = 'subscription'
    subscriptions = list_orders_with_status(wcapi, params)
    subscriptions = list(filter(lambda o: (str(datetime.strptime(o["date_created"], '%Y-%m-%dT%H:%M:%S').date(
    )) == str((datetime.now() - timedelta(1)).strftime('%Y-%m-%d'))), subscriptions))
    new_customers = get_new_customers(wcapi, orders)
    new_customers_list = []
    # Getting Vendor List....
    for o in orders:
        for item in o["meta_data"]:
            if item["key"] == "wos_vendor_data":
                o["vendor"] = item["value"]["vendor_name"]
            elif item["key"] == "_wc_acof_6" and item['value'] != "":
                o["vendor"] = item["value"]
        if 'vendor' not in o.keys():
            o['vendor'] = ""
    vendor_list = []
    for o in orders:
        if o['vendor'].lower().replace(" ", "").replace(".", "") not in vendor_list:
            vendor_list.append(o['vendor'].lower().replace(
                " ", "").replace(".", ""))
    # Creating Msg from Orders.....
    main_msg = ""
    for v in vendor_list:
        s_msg = "*Here are all the "+v+" orders to be delivered today:*\n"
        if v == "":
            s_msg = "*Here are the orders without any vendor assigned to them:*\n"
        for o in orders:
            customer_note = ""
            if o['customer_note']:
                customer_note = " ["+o['customer_note']+"] "
            customer_note = customer_note.replace("\r", " ")
            customer_note = customer_note.replace("\n", " ")
            if o['vendor'].lower().replace(" ", "").replace(".", "") == v:
                new_c = ""
                if o['customer_id'] in new_customers:
                    new_c = " `New Customer`"
                    new_customers_list.append({'total': o['total'], 'vendor': v})

                s_msg += str(o['id'])+" - "+o['billing']['first_name']+" " + \
                    o['billing']['last_name'] + \
                    " (Rs. "+o['total']+")"+customer_note+new_c+"\n"
        main_msg += s_msg
        send_msg_for_c(main_msg)
        main_msg = ""
    # Creating Msg for Subscriptions....
    s_msg = "*Here are the Subscriptions for today:*\n"
    for o in subscriptions:
        customer_note = ""
        if o['customer_note']:
            customer_note = " ["+o['customer_note']+"] "
            customer_note = customer_note.replace("\r", " ")
        new_c = ""
        if o['customer_id'] in new_customers:
            new_c = " `New Customer`"
        s_msg += str(o['id'])+" - "+o['billing']['first_name']+" " + \
            o['billing']['last_name'] + \
            " (Rs. "+o['total']+")"+customer_note+new_c+"\n"
    main_msg += s_msg
    main_msg += "`Please update the status for delivery of all these orders`"
    send_msg_for_c(main_msg)
    main_msg = ""
    total_a = 0
    total_v = {}
    for u in new_customers_list:
        total_a += float(u['total'])
        if u['vendor'] not in total_v.keys():
            total_v[u['vendor']] = {'total': float(u['total']), 'count': 1}
        else:
            total_v[u['vendor']] = {'total': total_v[u['vendor']]['total'] +
                                    float(u['total']), 'count': total_v[u['vendor']]['count']+1}
    main_msg = "*New Customers: " + \
        str(len(new_customers))+" [Rs. "+str(total_a)+"]*"
    for v in total_v.keys():
        if v == "":
            main_msg += ("\nwithout vendor " +
                         str(total_v[v]['count'])+" [Rs. "+str(total_v[v]['total'])+"]")
        else:
            main_msg += ("\n"+v+" "+str(total_v[v]['count']) +
                         " [Rs. "+str(total_v[v]['total'])+"]")
    send_slack_message(client, 'VENDOR_WISE', main_msg)


def send_every_day_at_9(orders, client, title):
    s_msg = title
    for o in orders:
        o['vendor'] = ""
        for item in o["meta_data"]:
            if item["key"] == "wos_vendor_data":
                o["vendor"] = item["value"]["vendor_name"]
            elif item["key"] == "_wc_acof_6" and item['value'] != "":
                o["vendor"] = item["value"]
        if o['vendor'] in ['mrdairy', 'Mr. Dairy']:
            continue
        customer_note = ""
        if o['customer_note']:
            customer_note = " ["+o['customer_note']+"] "
        s_msg += str(o['id'])+" - "+o['billing']['first_name']+" " + \
            o['billing']['last_name'] + \
            " (Rs. "+o['total']+")"+customer_note+"\n"
    send_slack_message(client, "VENDOR_WISE", s_msg)


def vendor_wise_tbd_tomorrow(orders, client):
    for o in orders:
        for item in o["meta_data"]:
            if item["key"] == "wos_vendor_data":
                o["vendor"] = item["value"]["vendor_name"]
            elif item["key"] == "_wc_acof_6" and item['value'] != "":
                o["vendor"] = item["value"]
        if 'vendor' not in o.keys():
            o['vendor'] = ""
    vendor_list = []
    for o in orders:
        if o['vendor'].lower().replace(" ", "").replace(".", "") not in vendor_list:
            vendor_list.append(o['vendor'].lower().replace(
                " ", "").replace(".", ""))
    main_msg = ""
    for v in vendor_list:
        s_msg = "*Here are all the "+v+" orders to be delivered tomorrow:*\n"
        if v == "":
            continue
        for o in orders:
            customer_note = ""
            if o['customer_note']:
                customer_note = " ["+o['customer_note']+"] "
            if o['vendor'].lower().replace(" ", "").replace(".", "") == v:
                s_msg += str(o['id'])+" - "+o['billing']['first_name']+" " + \
                    o['billing']['last_name'] + \
                    " (Rs. "+o['total']+")"+customer_note+"\n"
        main_msg += s_msg
        main_msg += "\n"
        send_slack_message(client, "VENDOR_WISE", main_msg)

