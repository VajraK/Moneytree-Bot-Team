const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

(async () => {
    const tokenHash = process.argv[2]; // Pass the token hash as a command-line argument
    const url = `https://www.dexanalyzer.io/token/${tokenHash}`;

    const browser = await puppeteer.launch();
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'networkidle2' });

    // Get the page content
    const content = await page.content();

    // Output the content to stdout
    console.log(content);

    await browser.close();
})();


/*
~Install Puppeteer using npm.
npm install puppeteer
npm install puppeteer-extra puppeteer-extra-plugin-stealth puppeteer

~On a fresh server, you might need to install additional libraries required by Chromium, the browser that Puppeteer uses.
sudo apt-get update
sudo apt-get install -y \
    libgbm1 \
    libasound2 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libxrandr2 \
    libgbm-dev \
    libnss3 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    fonts-liberation
*/