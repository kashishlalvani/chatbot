$(document).ready(function () {
    // Handle the send button click
    $("#send-btn").click(function () {
        sendMessage();
    });

    // Trigger send button on Enter key press
    $("#user-input").keypress(function (e) {
        if (e.which == 13) {
            sendMessage();
        }
    });

    function sendMessage() {
        let userMessage = $("#user-input").val().trim();

        if (userMessage) {
            // Display the user's message in the chat body
            $("#chat-body").append(`<div class="chat-message user-message">You: ${userMessage}</div>`);
            $("#user-input").val("");

            // Show loading spinner
            $("#chat-body").append(`<div class="chat-message loader" id="loading">Typing...</div>`);
            scrollChat();

            // Send the message to the backend for processing
            $.ajax({
                url: "/get_response",
                type: "POST",
                contentType: "application/json",
                data: JSON.stringify({ "message": userMessage }),
                success: function (response) {
                    // Remove loading spinner and display the bot's response
                    $("#loading").remove();
                    $("#chat-body").append(`<div class="chat-message bot-message">Bot: ${response.response}</div>`);
                    scrollChat();

                    // If the bot asks to learn, prompt for the correct answer
                    if (response.response.includes("Can you teach me")) {
                        let answer = prompt("Enter the correct answer (or type 'skip'):");
                        $.ajax({
                            url: "/teach_bot",
                            type: "POST",
                            contentType: "application/json",
                            data: JSON.stringify({ "question": userMessage, "answer": answer }),
                            success: function (res) {
                                $("#chat-body").append(`<div class="chat-message bot-message">Bot: ${res.response}</div>`);
                                scrollChat();
                            }
                        });
                    }
                }
            });
        }
    }

    function scrollChat() {
        $("#chat-body").animate({ scrollTop: $('#chat-body').prop("scrollHeight") }, 500);
    }
});
