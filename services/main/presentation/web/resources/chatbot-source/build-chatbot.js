minify = require('@node-minify/core');
htmlMinifier = require('@node-minify/html-minifier');
csso = require('@node-minify/csso');
terser = require('@node-minify/terser')
Datauri = require('datauri/sync');
fs = require('fs')
cheerio = require('cheerio');

try {
  html = fs.readFileSync('chatbot.html').toString();
  css = fs.readFileSync('css/chatbot.css').toString();
  js = fs.readFileSync('js/chatbot.js').toString();
} catch (error) {
  console.error("ERROR: please make sure you built the project using Prepros first.");
  console.error(error);
  return;
}

console.log("Processing CSS:")
minify({
  compressor: csso,
  content: css
}).then(function(min) {
  css = min;
  urls = css.split('url(')
  for (let i = 0; i < urls.length; i++) {
    if (urls[i].startsWith('images/')) {
      url = urls[i].split(')');
      console.log(`\tInlining: ${url[0]}`);
      url[0] = Datauri(url[0])['content'];
      url = url.join(')');
      urls[i] = url;
    }
  }
  css = urls.join('url(')

  console.log("Processing HTML:")
  $ = cheerio.load(html);
  $('img').each(function(i, elem) {
    console.log(`\tInlining: ${$(this).attr('src')}`);
    $(this).attr('src', Datauri($(this).attr('src'))['content'])
  });
  console.log('\tInlining CSS...')
  $('style').html(css);
  html = $.html()
  minify({
    compressor: htmlMinifier,
    content: html
  }).then(function(min) {
    html = min;
    console.log("Processing JS:");
    minify({
      compressor: terser,
      content: js,
      options: {
        toplevel: true,
        compress: true,
        mangle: true,
      }
    }).then(function(min) {
      min = min.replace('______chat_html______', (Buffer.from(html, 'binary').toString('base64')));
      min = "(function(){" + min + "})();"; // IIFE
      fs.writeFileSync('dist/drako.chatbot.js', min)
      console.log("\tDone!");
    });
  });
});