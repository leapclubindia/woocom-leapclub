$(document).ready(function () {
  $("#list_product_categories").on("submit", function (event) {
    event.preventDefault();
    $.NotificationApp.send(
      "Sending",
      "Please Wait For A While",
      "top-right",
      "success",
      "warning",
      10000
    );
    $.ajax({
      type: "GET",
      crossDomain: true,
      dataType: "text",
      url:
        "/list_product_categories?shipping_class=" +
        event.target.shipping_class.value,
      success: function (res) {
        var input = document.body.appendChild(document.createElement("input"));
        res = res.replace("&amp;", "&");
        input.value = res;
        input.select();
        var status = document.execCommand("copy");
        input.parentNode.removeChild(input);
        if (status) {
          $.NotificationApp.send(
            "Success",
            "Message Copied!",
            "top-right",
            "success",
            "success",
            10000
          );
        } else {
          $.NotificationApp.send(
            "Error",
            "Message Not Copied!",
            "top-right",
            "error",
            "error",
            10000
          );
        }
      },
      error: function (res) {
      },
    });
  });

  $("#datepicker").datepicker({
    dateFormat: "yy/mm/dd",
  });
  $("#datepicker1").datepicker({
    dateFormat: "yy/mm/dd",
  });
  $("#datepicker2").datepicker({
    dateFormat: "yy/mm/dd",
  });
  $('[data-toggle="tooltip"]').tooltip()
});
function copyText(text) {
  var input = document.body.appendChild(document.createElement("textarea"));
  input.value = text;
  input.select();
  var status = document.execCommand("copy");
  input.parentNode.removeChild(input);
  if (status) {
    $.nok({
      message: "Success, Url Copied!",
      type: "success",
    });
  } else {
    $.nok({
      message: "Error, Url Not Copied!",
      type: "error",
    });
  }
}

function updateSpan(order_id, template_name, color) {
  row = $(".wtmessage-" + order_id);
  span = $(
    '<span class="' + color + '">' + template_name + ", </span>"
  );
  row.append(span);
}

function SendWhatsappMessages(path) {
  $.nok({
    message: "Processing Your Request Please Wait!",
    type: "success",
  });
  $.ajax({
    type: "GET",
    crossDomain: true,
    dataType: "json",
    url: path,
    success: function (res) {
      if (["success", "PENDING", "SENT", true].includes(res.result)) {
        $.nok({
          message: "Success, Message Sent!",
          type: "success",
        });
        updateSpan(res.order_id, res.template_name, 'text-success')
      } else {
        $.nok({
          message: "Error, Message Not Sent!",
          type: "error",
        });
        updateSpan(res.order_id, res.template_name, 'text-danger')
      }
    },
    error: function (res) {
      $.nok({
        message: "API Error, Message Not Sent!",
        type: "error",
      });
    },
  });
}


function sendToGoogleSheet(act, status) {
  var inp_select = $('#select_inps')
  var inp_select_v = inp_select.val()
  $.nok({
    message: "Processing Your Request Please Wait!",
    type: "success",
  });
  $.ajax({
    type: "POST",
    crossDomain: true,
    dataType: "json",
    url: "/csv",
    data: { 'order_ids': inp_select_v, 'action': [act], 'status': status },
    success: function (res) {
      if (res.result == 'success') {
          delivery_dates_text = ""
          delivery_date_msg = ""
          for (var d of Object.keys(res.delivery_dates)) {
            dt = d
            if (d == '') {
              dt = "No Date"
            }
            delivery_dates_text += (dt + " : " + res.delivery_dates[d]['count'].toString() + " orders <br>")
          }
          if (Object.keys(res.delivery_dates).length > 1) {
            delivery_date_msg = "There are orders with different delivery date or no delivery date. Please change it now."
          }
          status_text = ""
          status_msg = ""
          for (var d of Object.keys(res.status_list)) {
            status_text += (d + " : " + res.status_list[d]['count'].toString() + " orders <br>")
          }
          if (Object.keys(res.status_list).length > 1) {
            status_msg = "There are orders with different status. Please change all orders to To Be Delivered. "
          }
          Swal.fire({
            html: `
<b>`+ res.total_o + ` orders added to Google Sheet <a target='blank' href='` + res.ssUrl + `'>` + res.ssName + `</a></b><br/><br/>
<div style='text-align: left'><b>Delivery Dates</b><br/>
`+ delivery_dates_text + `<br>
`+ delivery_date_msg + `</div><br/><br/>
<div style='text-align: left'><b>Status</b><br/>
`+ status_text + `<br>
`+ status_msg + `</div>
            `,
            width: 700,
            backdrop: `
              rgba(0,0,123,0.4)
            `
          })
      } else {
        $.nok({
          message: "Error, Sheet Not Created!",
          type: "error",
        });
      }
    },
    error: function (res) {
      $.nok({
        message: "API Error, Please Ask To Admin!",
        type: "error",
      });
    },
  });
}

function copyOrderDetail(status) {
  var inp_select = $('#select_inps')
  var inp_select_v = inp_select.val()
  $.nok({
    message: "Processing Your Request Please Wait!",
    type: "success",
  });
  $.ajax({
    type: "POST",
    crossDomain: true,
    dataType: "json",
    url: "/order_details",
    data: { 'order_ids': inp_select_v, 'status': status },
    success: function (res) {
      text = res.result.replace("&amp;", "&")
      var input = document.body.appendChild(document.createElement("textarea"));
      input.value = text;
      input.select();
      var status = document.execCommand("copy");
      input.parentNode.removeChild(input);
      if (status) {
        $.nok({
          message: "Success, Message Copied!",
          type: "success",
        });
      } else {
        if (text.length > 0) {
          Swal.fire({
            html: `
        <pre>
        <div style='text-align: left;'>
<b class='text-danger'>There are some problem in flask panel, please copy manualy</b>

`+ text + `
</pre>
</div>
        `,
            width: 700,
            backdrop: `
          rgba(0,0,123,0.4)
        `
          })
        } else {
          $.nok({
            message: "Error, Message Not Copied!",
            type: "error",
          });
        }
      }
    },
    error: function (err) {
      $.nok({
        message: "API Error, Please Ask To Admin!",
        type: "error",
      });
    },
  });
}

function copyOrderDetailMini(status) {
  var inp_select = $('#select_inps')
  var inp_select_v = inp_select.val()
  $.nok({
    message: "Processing Your Request Please Wait!",
    type: "success",
  });
  $.ajax({
    type: "POST",
    crossDomain: true,
    dataType: "json",
    url: "/order_details_mini",
    data: { 'order_ids': inp_select_v, 'status': status },
    success: function (res) {
      text = res.result.replace("&amp;", "&")
      var input = document.body.appendChild(document.createElement("textarea"));
      input.value = text;
      input.select();
      var status = document.execCommand("copy");
      input.parentNode.removeChild(input);
      if (status) {
        $.nok({
          message: "Success, Message Copied!",
          type: "success",
        });
      } else {
        if (text.length > 0) {
          Swal.fire({
            html: `
        <pre>
        <div style='text-align: left;'>
<b class='text-danger'>There are some problem in flask panel, please copy manualy</b>

`+ text + `
</pre>
</div>
        `,
            width: 700,
            backdrop: `
          rgba(0,0,123,0.4)
        `
          })
        } else {
          $.nok({
            message: "Error, Message Not Copied!",
            type: "error",
          });
        }
      }
    },
    error: function (err) {
      $.nok({
        message: "API Error, Please Ask To Admin!",
        type: "error",
      });
    },
  });
}

function copyCustomerDetail(status) {
  var inp_select = $('#select_inps')
  var inp_select_v = inp_select.val()
  $.nok({
    message: "Processing Your Request Please Wait!",
    type: "success",
  });
  $.ajax({
    type: "POST",
    crossDomain: true,
    dataType: "json",
    url: "/customer_details",
    data: { 'order_ids': inp_select_v, 'status': status },
    success: function (res) {
      text = res.result.replace("&amp;", "&")
      var input = document.body.appendChild(document.createElement("textarea"));
      input.value = text;
      input.select();
      var status = document.execCommand("copy");
      input.parentNode.removeChild(input);
      if (status) {
        $.nok({
          message: "Success, Message Copied!",
          type: "success",
        });
      } else {
        if (text.length > 0) {
          Swal.fire({
            html: `
        <pre>
        <div style='text-align: left;'>
<b class='text-danger'>There are some problem in flask panel, please copy manualy</b>

`+ text + `
</pre>
</div>
        `,
            width: 700,
            backdrop: `
          rgba(0,0,123,0.4)
        `
          })
        } else {
          $.nok({
            message: "Error, Message Not Copied!",
            type: "error",
          });
        }
      }
    },
    error: function (err) {
      $.nok({
        message: "API Error, Please Ask To Admin!",
        type: "error",
      });
    },
  });
}

function copySupplierMessage(status) {
  var inp_select = $('#select_inps')
  var inp_select_v = inp_select.val()
  $.nok({
    message: "Processing Your Request Please Wait!",
    type: "success",
  });
  $.ajax({
    type: "POST",
    crossDomain: true,
    dataType: "json",
    url: "/supplier_messages",
    data: { 'order_ids': inp_select_v, 'status': status },
    success: function (res) {
      text = res.result.replace("&amp;", "&")
      var input = document.body.appendChild(document.createElement("textarea"));
      input.value = text;
      input.select();
      var status = document.execCommand("copy");
      input.parentNode.removeChild(input);
      if (status) {
        $.nok({
          message: "Success, Message Copied!",
          type: "success",
        });
      } else {
        if (text.length > 0) {
          Swal.fire({
            html: `
        <pre>
        <div style='text-align: left;'>
<b class='text-danger'>There are some problem in flask panel, please copy manualy</b>

`+ text + `
</pre>
</div>
        `,
            width: 700,
            backdrop: `
          rgba(0,0,123,0.4)
        `
          })
        } else {
          $.nok({
            message: "Error, Message Not Copied!",
            type: "error",
          });
        }
      }
    },
    error: function (err) {
      $.nok({
        message: "API Error, Please Ask To Admin!",
        type: "error",
      });
    },
  });
}


function genMultipleLinks() {
  var inp_select = $('#select_inps')
  var inp_select_v = inp_select.val()
  $.nok({
    message: "Processing Your Request Please Wait!",
    type: "success",
  });
  $.ajax({
    type: "POST",
    crossDomain: true,
    dataType: "json",
    url: "/multiple_links",
    data: { 'order_ids': inp_select_v },
    success: function (res) {
      if (!Object.keys(res).includes('status')) {
        new_tr = ""
        for (var c of res.results) {
          if (c.result == 'success') {
            for (var id of c.order_ids) {
              var tag = $('#payment-' + id.toString())
              tag.text(c.receipt + " | " + (c.amount / 100).toString())
              tag.attr('onclick', "copyText('" + c.short_url + "')")
              tag.attr('class', 'text-success')
            }
            new_tr += `
          <tr>
            <td><p>`+ c.mobile.toString() + `</p></td>
            <td><p>`+ (c.amount / 100).toString() + `</p></td>
            <td><p>`+ c.receipt + `</p></td>
            <td><button class='btn btn-success btn-sm' title='Click To Copy Payment Link' onclick="copyText('`+ c.short_url + `')">Copy Link</button></td>
          </tr>`
          } else {
            new_tr += `
          <tr class='table-danger'>
            <td><p>`+ c.mobile.toString() + `</p></td>
            <td><p>`+ (c.amount / 100).toString() + `</p></td>
            <td><p>`+ c.receipt + `</p></td>
          </tr>`
          }
        }
        Swal.fire({
          html: `
          <table class='table'>
            <thead>
            <tr>
              <th><b>Mobile</b></th>  
              <th><b>Amount</b></th>  
              <th><b>Receipt</b></th>  
            </tr>  
            </thead>
            <tbody>
            `+ new_tr + `
            </tbody>
          </table>
        `,
          width: 700,
          backdrop: `
          rgba(0,0,123,0.4)
        `,
          confirmButtonColor: '#FF3232',
          confirmButtonText: 'Close'
        })
      }else{
        Swal.fire({
          icon: "warning",
          html: "<b>Following orders are already paid. Please exclude them from selection: <b>"+res.result
        })
      }
    }
  })
}

function changeOrderStatus(status) {
  var inp_select = $('#select_inps')
  var inp_select_v = inp_select.val()
  $.nok({
    message: "Processing Your Request Please Wait!",
    type: "success",
  });
  $.ajax({
    type: "POST",
    crossDomain: true,
    dataType: "json",
    url: "/change_order_status",
    data: { 'order_ids': inp_select_v, "status": status },
    success: function (res) {
      if (res.result == 'success') {
        trtext = ""
        for (var o of res.result_list) {
          trtext += `
              <tr>
                <td><p>`+ o.order_id + " ( " + o.name + ` ) </p></td>
                <td><p>`+ o.status + `</p></td>
                <td><p>`+ o.message + `</p></td>
                <td><p>`+ o.refund + `</p></td>
              </tr>
          `
        }
        Swal.fire({
          html: `
            <table class='table'>
              <thead>
              <tr>
                <th><b>Order ID ( Name )</b></th>  
                <th><b>Result</b></th>  
                <th><b>Message</b></th>  
                <th><b>Refund</b></th>  
              </tr>  
              </thead>
              <tbody>
              `+ trtext + `
              </tbody>
            </table>
          `,
          width: 700,
          backdrop: `
            rgba(0,0,123,0.4)
          `
        }).then(() => {
          location.reload()
        })
      }
      else {
        $.nok({
          message: "Error, Order Status Not Changed Please Check Order ID!",
          type: "error",
        });
      }
    }
  })
}

function copyToClipboard(id) {
  $.nok({
    message: "Please Wait For a While, Generating Message ....",
    type: "success",
  });
  $.ajax({
    type: "GET",
    crossDomain: true,
    dataType: "json",
    url: "/get_copy_messages/" + id.toString(),
    success: function (res) {
      if (res.status == 'success') {
        var input = document.body.appendChild(document.createElement("textarea"));
        input.value = res.text;
        input.select();
        var status = document.execCommand("copy");
        input.parentNode.removeChild(input);
        if (status) {
          $.nok({
            message: "Success, Message Copied!",
            type: "success",
          });
        } else {
          if (res.text.length > 0) {
            Swal.fire({
              html: `
          <pre>
          <div style='text-align: left;'>
<b class='text-danger'>There are some problem in flask panel, please copy manualy</b>

`+ res.text + `
</pre>
</div>
          `,
              width: 700,
              backdrop: `
            rgba(0,0,123,0.4)
          `
            })
          } else {
            $.nok({
              message: "Error, Message Not Copied!",
              type: "error",
            });
          }
        }
      } else {
        $.nok({
          message: "Error, Message Not Copied!",
          type: "error",
        });
      }
    },
    error: function (res) {
      $.nok({
        message: "API Error, Message Not Sent!",
        type: "error",
      });
    },
  });
}

function CheckOutRequest(url) {
  $.nok({
    message: "Processing Your Request Please Wait!",
    type: "success",
  });
  $.ajax({
    type: "GET",
    crossDomain: true,
    dataType: "json",
    url: url,
    success: function (res) {
      if (res.result == 'check') {
        o_str = ""
        for (var o of res.orders) {
          o_str += '<tr>'
          o_str += '<td>' + o['id'] + '</td>'
          o_str += '<td>' + o['status'] + '</td>'
          o_str += '<td>' + o['total'] + '</td>'
          o_str += '</tr>'
        }
        Swal.fire({
          html: `
        <b>Follow orders of `+ res.orders[0]['billing']['first_name'] + " " + res.orders[0]['billing']['last_name'] + ` are unpaid. Do you want to generate payment for a single order?</b>
          <table class='table'>
            <thead>
            <tr>
              <th><b>Order ID</b></th>  
              <th><b>Status</b></th>  
              <th><b>Amount</b></th>  
            </tr>  
            </thead>
            <tbody>
            `+ o_str + `
            </tbody>
          </table>
        `,
          width: 700,
          backdrop: `
          rgba(0,0,123,0.4)
        `,
          confirmButtonText: 'Yes',
          cancelButtonText: 'No',
          showCancelButton: true,
        }).then((result) => {
          if (result.isConfirmed) {
            $.ajax({
              type: "GET",
              crossDomain: true,
              dataType: "json",
              url: url + "?check=true",
              success: function (res) {
                if (res.result == "success") {
                  $.nok({
                    message: res.text,
                    type: "success",
                  });
                  var tag = $('#payment-' + res.order_id)
                  tag.text(res.payment.receipt + " | " + (res.payment.amount / 100).toString())
                  tag.attr('onclick', "copyText('" + res.short_url + "')")
                  tag.attr('class', 'text-success')
                } else {
                  $.nok({
                    message: "Error, Link Not Generated!",
                    type: "error",
                  });
                  var tag = $('#payment-' + res.order_id)
                  tag.text(res.payment.receipt)
                  tag.attr('class', 'text-danger')
                }
              }
            })
          }
        })
      }
      else if (res.result == "success") {
        $.nok({
          message: res.text,
          type: "success",
        });
        var tag = $('#payment-' + res.order_id)
        tag.text(res.payment.receipt + " | " + (res.payment.amount / 100).toString())
        tag.attr('onclick', "copyText('" + res.short_url + "')")
        tag.attr('class', 'text-success')
      } else if (res.result == 'paid') {
        Swal.fire({
          title: 'The order is already paid. Payment link cannot be generated.',
          icon: 'warning',
        })
      } else {
        $.nok({
          message: "Error, Link Not Generated!",
          type: "error",
        });
        var tag = $('#payment-' + res.order_id)
        tag.text(res.payment.receipt)
        tag.attr('class', 'text-danger')
      }
    },
    error: function (res) {
      $.nok({
        message: "API Error, Please Try Again!",
        type: "error",
      });
    },
  });
}


function genSubscriptionLink(id) {
  Swal.fire({
    title: 'Enter amount',
    input: 'text',
    inputAttributes: {
      autocapitalize: 'off'
    },
    showCancelButton: true,
    confirmButtonText: 'Generate',
    showLoaderOnConfirm: true,
    preConfirm: (amount) => {
      return ($.ajax({
        type: "GET",
        crossDomain: true,
        dataType: "json",
        url: "/genSubscriptionLink/" + id + "/" + amount,
        success: function (res) {
          if (res.result == "success") {
            console.log(res);
            return res
          } else {
            Swal.showValidationMessage(
              `Please enter valid amount.`
            )
          }
        }
      }))
    },
    allowOutsideClick: () => !Swal.isLoading()
  }).then((res) => {
    if (res.isConfirmed) {
      res = res.value
      if (res.result == "success") {
        Swal.fire({
          title: "Success, Link Generated!",
          icon: "success",
        });
        var tag = $('#payment-' + res.data.id)
        tag.text(res.data.receipt + " | " + (res.data.amount / 100).toString())
        tag.attr('onclick', "copyText('" + res.data.short_url + "')")
        tag.attr('class', 'text-success')
      } else {
        Swal.fire({
          title: "Error, Link Not Generated!",
          icon: "error",
        });
        var tag = $('#payment-' + res.data.id)
        tag.text(res.data.receipt)
        tag.attr('class', 'text-danger')
      }
    }
  })
}


function genMulSubscriptionLinks() {
  var inp_select = $('#select_inps')
  var inp_select_v = inp_select.val()
  $.nok({
    message: "Processing Your Request Please Wait!",
    type: "success",
  });
  $.ajax({
    type: "POST",
    crossDomain: true,
    dataType: "json",
    url: "/genMulSubscriptionLink",
    data: { 'order_ids': inp_select_v },
    success: function (res) {
      new_tr = ""
      for (var c of res.results) {
        if (c.result == 'success') {
          for (var id of c.order_ids) {
            var tag = $('#payment-' + id.toString())
            tag.text(c.receipt + " | " + (c.amount / 100).toString())
            tag.attr('onclick', "copyText('" + c.short_url + "')")
            tag.attr('class', 'text-success')
          }
          new_tr += `
          <tr>
            <td><p>`+ c.mobile.toString() + `</p></td>
            <td><p>`+ (c.amount / 100).toString() + `</p></td>
            <td><p>`+ c.receipt + `</p></td>
            <td><button class='btn btn-success btn-sm' title='Click To Copy Payment Link' onclick="copyText('`+ c.short_url + `')">Copy Link</button></td>
          </tr>`
        } else {
          new_tr += `
          <tr class='table-danger'>
            <td><p>`+ c.mobile.toString() + `</p></td>
            <td><p>`+ (c.amount / 100).toString() + `</p></td>
            <td><p>`+ c.receipt + `</p></td>
          </tr>`
        }
      }
      Swal.fire({
        html: `
          <table class='table'>
            <thead>
            <tr>
              <th><b>Mobile</b></th>  
              <th><b>Amount</b></th>  
              <th><b>Receipt</b></th>  
            </tr>  
            </thead>
            <tbody>
            `+ new_tr + `
            </tbody>
          </table>
        `,
        width: 700,
        backdrop: `
          rgba(0,0,123,0.4)
        `,
        confirmButtonColor: '#FF3232',
        confirmButtonText: 'Close'
      })
    }
  })
}


function copyLinkedOrders() {
  var inp_select = $('#select_inps')
  var inp_select_v = inp_select.val()
  $.nok({
    message: "Please Wait For a While, Generating Message ....",
    type: "success",
  });
  $.ajax({
    type: "POST",
    crossDomain: true,
    dataType: "json",
    url: "/copy_linked_orders",
    data: {'order_ids': inp_select_v},
    success: function (res) {
      if (res.status == 'success') {
        var input = document.body.appendChild(document.createElement("textarea"));
        input.value = res.text;
        input.select();
        var status = document.execCommand("copy");
        input.parentNode.removeChild(input);
        if (status) {
          $.nok({
            message: "Success, Message Copied!",
            type: "success",
          });
        } else {
          if (res.text.length>0){
            Swal.fire({
          html: `
          <pre>
          <div style='text-align: left;'>
<b class='text-danger'>There are some problem in flask panel, please copy manualy</b>

`+res.text+`
</pre>
</div>
          `,
          width: 700,
          backdrop: `
            rgba(0,0,123,0.4)
          `
        })
          }else{
          $.nok({
            message: "Error, Message Not Copied!",
            type: "error",
          });
        }
        }
      } else {
        $.nok({
          message: "Error, Message Not Copied!",
          type: "error",
        });
      }
    },
    error: function (res) {
      $.nok({
        message: "API Error, Message Not Sent!",
        type: "error",
      });
    },
  });
}



function sendWMessages(name) {
  var inp_select = $('#select_inps')
  var inp_select_v = inp_select.val()
  $.nok({
    message: "Processing Your Request Please Wait!",
    type: "success",
  });
  $.ajax({
    type: "POST",
    crossDomain: true,
    dataType: "json",
    url: "/send_whatsapp_messages/" + name,
    data: { 'order_ids': inp_select_v },
    success: function (res) {
      if (res.result == 'success') {
        trtext = ""
        for (var o of res.results) {
          console.log(o);
          if (["success", "PENDING", "SENT", true].includes(o.result)) {
            updateSpan(o.order_id, o.template_name, 'text-success')
          } else {
            updateSpan(o.order_id, o.template_name, 'text-danger')
          }
          button = `<td onclick="sendWPaymentLink('`+o.order_id+"','"+o.phone_number+"','"+o.vendor_type+`')"><button class='btn btn-sm btn-success'>Send Payment Link</button></td>`
          if (!o.button){
            button = ""
          }
          trtext += `
              <tr>
                <td><p>`+ o.customer_name + " ( " + o.phone_number + ` ) </p></td>
                <td><p>`+ o.order_id + `</p></td>
                <td><p>`+ o.result + `</p></td>
                <td><p>`+ o.payment_status + `</p></td>
                `+button+`
              </tr>
          `
        }
        Swal.fire({
          html: `
          <b>Group orders by customer:</b>
            <table class='table'>
              <thead>
              <tr>
                <th><b>Name (Mobile)</b></th>  
                <th><b>Order IDS</b></th>  
                <th><b>Result</b></th>  
                <th><b>Paid/Unpaid</b></th>  
              </tr>  
              </thead>
              <tbody>
              `+ trtext + `
              </tbody>
            </table>
          `,
          width: 1000,
          backdrop: `
            rgba(0,0,123,0.4)
          `,
          allowOutsideClick: false
        })
      }
      else {
        $.nok({
          message: "Error, Messages not sent!",
          type: "error",
        });
      }
    }
  })
}
function sendWPaymentLink(id, phone_number, order_type){
  console.log(id, phone_number, order_type);
    $.nok({
    message: "Processing Your Request Please Wait!",
    type: "success",
  });
  $.ajax({
    type: "POST",
    crossDomain: true,
    dataType: "json",
    url: "/send_payment_link_wt/"+id,
    data: {'mobile_number': phone_number, 'order_type': order_type},
    success: function (res) {
      if (["success", "PENDING", "SENT", true].includes(res.result)) {
        $.nok({
          message: "Success, Payment Link Sent!",
          type: "success",
        });
        updateSpan(res.order_id, res.template_name, 'text-success')
      } else {
        $.nok({
          message: "Error, Message Not Sent!",
          type: "error",
        });
        updateSpan(res.order_id, res.template_name, 'text-danger')
      }
    },
    error: function (res) {
      $.nok({
        message: "API Error, Message Not Sent!",
        type: "error",
      });
    },
  });
}
