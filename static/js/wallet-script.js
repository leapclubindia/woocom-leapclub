function MoneyToWallet(id, action) {
  Swal.mixin({
    input: 'text',
    confirmButtonText: 'Next &rarr;',
    showCancelButton: true,
    progressSteps: ['1', '2']
  }).queue([
    'Enter Amount: ',
    'Enter Details: '
  ]).then((result) => {
    if (result.value) {
      Swal.fire({
        title: 'Processing Your Request....',
        showConfirmButton: false,
        allowOutsideClick: false,
        didOpen: () => {
          Swal.showLoading()
        },
      })
      $.ajax({
        type: "POST",
        crossDomain: true,
        dataType: "json",
        url: "/wallet",
        data: { 'id': id, 'amount': result.value[0], 'action': action, 'details': result.value[1] },
        success: function (res) {
          if (res.result == 'success') {
            Swal.fire({
              icon: "success",
              title: "Rs " + result.value[0] + " " + action.toUpperCase() + "ED Successfuly!"
            })
            $('#balance-' + id).html("₹ " + res.balance)
          } else {
            Swal.fire({
              icon: "error",
              title: "Got Error From Wallet Please Check Amount and details!"
            })
          }
        },
        error: function () {
          Swal.fire({
            icon: "error",
            title: "Got Error From Wallet Please Check Amount and details!"
          })
        }
      })
    }
  })
}

function genPaymentLinkWallet(id) {
  Swal.fire({
    title: 'Amount: ',
    input: 'text',
    inputAttributes: {
      autocapitalize: 'off'
    },
    showCancelButton: true,
    confirmButtonText: 'Next &rarr;',
  }).then((result) => {
    if (result.value) {
      Swal.fire({
        title: 'Processing Your Request....',
        showConfirmButton: false,
        allowOutsideClick: false,
        didOpen: () => {
          Swal.showLoading()
        },
      })
      $.ajax({
        type: "POST",
        crossDomain: true,
        dataType: "json",
        url: "/wallet/genlink",
        data: { 'id': id, 'amount': result.value },
        success: function (res) {
          if (res.result == 'success') {
            Swal.fire({
              icon: "success",
              title: "Success",
              html: `<button class='btn btn-success btn-lg' title='Click To Copy Payment Link' onclick="copyText('` + res.link + `')">Copy Link</button>`
            })
          } else {
            Swal.fire({
              icon: "error",
              title: "Got Error From Razorpay Please Check Amount!"
            })
          }
        },
        error: function () {
          Swal.fire({
            icon: "error",
            title: "Got Error From Razorpay Please Check Amount!"
          })
        }
      })
    }
  })
}
