@echo off
del css\chatbot.css
del chatbot.html
del dist\drako.chatbot.js
del js\chatbot.compat.js
call npm install
call npx sass css/chatbot.scss css/chatbot.css
call npx pug chatbot.pug
node build-chatbot.js