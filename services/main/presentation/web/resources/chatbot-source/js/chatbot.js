(function() {
  API_URL = "https://www.drako.ai/api/";
  POPUP_TIMEOUT = 3;
  isFirstTime = true;
  initChatbot = function() {
    // console.log("[chat] Initializing...");
    if ($('body').length < 1) {
      // console.log("[chat] Aborted initialization, no body element found.")
      return;
    }
    $('body').append($(atob('______chat_html______')));
    template = $('.chatbot .chatbot-container .discussion-message-template').clone()
    $('.chatbot .chatbot-container .discussion-message-template').remove()
    function scrollUp() {
      setTimeout(function() {
        $('.chatbot .chatbot-container .chatbot-body--discussion')[0].scrollTop = $('.chatbot .chatbot-container .chatbot-body--discussion')[0].scrollHeight
      }, 1)
    }
    $('.chatbot .chatbot-toggle').on('click', function(e) {
      $('.chatbot').toggleClass('maximized minimized')
      if ($('.chatbot').hasClass('maximized') && isFirstTime) {
        isFirstTime = false;
        scrollUp();
      }
    })

    function htmlEncode(str){
      return String(str).replace(/[^\w. ]/gi, function(c){
         return '&#'+c.charCodeAt(0)+';';
      });
    }
    // $('.inputline-text,.inputline-attachment').removeClass('show').addClass('hide')
    // $('.inputline-options').removeClass('hide').addClass('show')
    function addMessage(msg, fromBot, isHistory) {
      // console.log("Processing message:", msg);
      e = template.clone();
      if (fromBot) {
        e.addClass('discussion-message--bot');
      } else {
        e.addClass('discussion-message--user');
        e.find('.avatar').remove();
      }
      if (!msg.message) {
        e.find('.message-text').remove();
      } else {
        var message_input = msg.message; //htmlEncode(msg.message);
        // console.log(msg.message);
        // console.log(message_input);
        e.find('.message-text').html(message_input);
      }
      if (!msg.cards || !msg.cards[0] || !msg.cards[0].buttons) {
        e.find('.message-options').remove();
      } else {
        if (isHistory) {
          e.find('.message-options').addClass('disabled');
        }
        for (const button of msg.cards[0].buttons) {
          option = $('<div>').addClass('message-option').text(button['text']).attr('data-content', button['value'])
          if (button['selected']) {
            option.addClass('selected');
          }
          option.on('click', function() {
            $(this).addClass('selected');
            $(this).closest('.message-options').addClass('disabled');
            $('.chatbot-body--inputline .inputline-text input').val($(this).attr('data-content'));
            $('.chatbot-body--inputline .inputline-text .input-btn-sendmessage').click();
          })
          e.find('.message-options').append(option)
          // console.log(button)
        }
      }
      if (!msg.attachment) {
        e.find('.message-attachment').remove();
      } else {
        e.find('.message-attachment').text(msg.attachment);
      }
      if (msg.action_required && msg.action_required == "file_upload") {
        $('.inputline-text,.inputline-attachment').removeClass('show').addClass('hide')
        $('.inputline-options').removeClass('hide').addClass('show')
      }
      $('.chatbot .chatbot-container .chatbot-body--discussion .chatbot-messages').append(e);
      scrollUp()
      $('.chatbot-body--inputline .inputline-text input').focus()
      setTimeout(function(){
        if ($(window).width() > 768) {
          $('.chatbot').removeClass('minimized').addClass('maximized')
          scrollUp()
       }
      }, POPUP_TIMEOUT*1000)
    }

    function getHistory() {
      $.ajax({
        url: API_URL + 'history',
        type: 'GET',
        crossDomain: true,
        dataType: 'text',
        xhrFields: {
          withCredentials: true
        },
        success: function(data) {
          // Initial greeting
          var response = JSON.parse(data);
          lines = response['history'];

          if (lines.length > 0) {
            addMessage({
              message: 'Hi! I\'m Drako.ai v1, let me know if you need help to hack a machine!<br/>Remember that to use v2 you need to sign up for the beta!',
            }, true);
          } else {
            addMessage({
              message: 'Hi! I\'m Drako.ai v1, let me know if you need help to hack a machine!<br/>Remember that to use v2 you need to sign up for the beta!',
              cards:   [{buttons:[{text: "Guide me!",value:"I would like to know what I should do next"},{text:"About my target",value:"I want to tell you more about my target"},{text:"What do you know?",value:"I would like to understand what you know about my target"},{text:"How does this work?",value:"How does this work"}]}],
            }, true);
          }

          for (const line of lines) {
            if (line.startsWith("user:")) {
              addMessage({
                message: line.replace('user:', '')
              }, false)
            } else if (line.startsWith("drako:")) {
              addMessage({
                message: line.replace('drako:', '')
              }, true)
            }
          }
          $('.chatbot-preloader').remove();
        },
        error: function(e) {
          console.log(e);
        }
      });
    }

    $('.chatbot-body--inputline .inputline-text input').keypress(function(e) {
      if (e.keyCode == 13) {
        $('.chatbot-body--inputline .inputline-text .input-btn-sendmessage').click();
      }
    });


    $('.chatbot-body--inputline .inputline-text input').on('change', function(e) {
      if ($(this).val().trim() != '') {
        $('.chatbot-body--inputline .inputline-text .input-placeholder').addClass('hidden');
      } else {
        $('.chatbot-body--inputline .inputline-text .input-placeholder').removeClass('hidden');
      }
    });

    $('.input-btn-attachmentremove').on('click', function() {
      // console.log('clearing input');
      $('#input-attachment').val('').change()
    })
    $('.input-option--attachment').on('click', function() {
      $('#input-attachment').click();
    })

    $('.inputline-options .input-option--secondary').on('click', function() {
      $('.chatbot-message-preloader.dots').removeClass('hidden')
      addMessage({
        message: 'No, thanks.'
      }, false);
      $('.inputline-attachment,.inputline-options').removeClass('show').addClass('hide')
      $('.inputline-text').removeClass('hide').addClass('show')
      $.ajax({
        url: API_URL + 'send_message',
        data: {
          message: 'No, thanks.',
          error: "upload_refused"
        },
        type: 'POST',
        crossDomain: true,
        dataType: 'text',
        xhrFields: {
          withCredentials: true
        },
        success: function(data) {
          var response = JSON.parse(data)
          // console.log(response);
          addMessage(response, true);
          $('.chatbot-message-preloader.dots').addClass('hidden')
        },
        error: function(e) {
          $('.chatbot-message-preloader.dots').addClass('hidden')
          console.log(e);
          alert('Error: ' + e);
        }
      });
    })


    $('#input-attachment').on('change', function() {
      if ($('#input-attachment')[0].files[0]) {
        $('.inputline-attachment .text').text($('#input-attachment').get(0).files.item(0).name)
        $('.inputline-text,.inputline-options').removeClass('show').addClass('hide')
        $('.inputline-attachment').removeClass('hide').addClass('show')
      } else {
        $('.inputline-text,.inputline-attachment').removeClass('show').addClass('hide')
        $('.inputline-options').removeClass('hide').addClass('show')
      }
    })

    $('.chatbot-body--inputline .inputline-text .input-btn-sendmessage').on('click', function(e) {
      input_text = $('.chatbot-body--inputline .inputline-text input').val().trim();

      // console.log(input_text);
      input_text = input_text.replace(/[^0-9a-z.\/ !_()@]/gi, '');
      // console.log(input_text);
      $('.chatbot-body--inputline .inputline-text input').val('')

      if (input_text == "") {
        // console.log("Empty message, skipping");
        return;
      }
      // console.log("Continues");

      addMessage({
        message: input_text
      }, false);
      $('.chatbot-message-preloader.dots').removeClass('hidden')
      $.ajax({
        url: API_URL + 'send_message',
        data: {
          message: input_text
        },
        type: 'POST',
        crossDomain: true,
        dataType: 'text',
        xhrFields: {
          withCredentials: true
        },
        success: function(data) {
          $('.chatbot-message-preloader.dots').addClass('hidden')
          var response = JSON.parse(data)
          // console.log(response);
          addMessage(response, true);
        },
        error: function(e) {
          $('.chatbot-message-preloader.dots').addClass('hidden')
          console.log(e);
          alert('Error: ' + e);
        }
      });
    });

    $('.chatbot-body--inputline .inputline-attachment .input-btn-sendmessage').on('click', function(e) {
      if (!$('#input-attachment')[0].files[0]) {
        console.log("Empty message, skipping");
        return;
      }
      $('.inputline-attachment,.inputline-options').removeClass('show').addClass('hide')
      $('.inputline-text').removeClass('hide').addClass('show')
      addMessage({
        attachment: $('#input-attachment').get(0).files.item(0).name
      }, false);
      $('.chatbot-message-preloader.dots').removeClass('hidden')
      reader = new FileReader();
      reader.onloadend = function() {
        $('#input-attachment').val('')
        $.ajax({
          url: API_URL + 'send_message',
          data: {
            file: reader.result,
            message: "Upload this file"
          },
          type: 'POST',
          crossDomain: true,
          dataType: 'text',
          xhrFields: {
            withCredentials: true
          },
          success: function(data) {
            $('.chatbot-message-preloader.dots').addClass('hidden')
            var response = JSON.parse(data)
            // console.log(response);
            addMessage(response, true);
          },
          error: function(e) {
            $('.chatbot-message-preloader.dots').addClass('hidden')
            console.log(e);
            alert('File upload error: ' + e);
          }
        });
      }
      reader.readAsDataURL($('#input-attachment').get(0).files.item(0))
    });
    getHistory();
  }
  // console.log("[chat] Checking for jQuery...");
  if (window.jQuery) {
    initChatbot();
  } else {
    // console.log("[chat] Attempting to load jQuery...");
    script = document.createElement('script');
    script.onload = script.onreadystatechange = initChatbot;
    script.src = "https://code.jquery.com/jquery-3.5.1.min.js";
    document.head.appendChild(script);
  }
})();