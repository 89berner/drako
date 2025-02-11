#!/bin/bash
rm css/chatbot.css
rm chatbot.html
rm dist/drako.chatbot.js
mkdir dist

npm install .
# npx sass css/chatbot.scss css/chatbot.css
sass "css/chatbot.scss" "css/chatbot.css"
# npx pug chatbot.pug
pug chatbot.pug

node build-chatbot.js