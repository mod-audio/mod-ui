var page = require('webpage').create(),
    system = require('system'),
    address, output, size;

if (system.args.length != 5) {
    console.log('Usage: screenshot.js URL filename [paperwidth*paperheight|paperformat] [zoom]');
    console.log('  paper (pdf output) examples: "5in*7.5in", "10cm*20cm", "A4", "Letter"');
    phantom.exit(1);
} else {
    address = system.args[1];
    output = system.args[2];
    width = system.args[3];
    height = system.args[4];
    page.viewportSize = { width: width, height: height };
    page.open(address, function (status) {
        if (status !== 'success') {
            console.log('Unable to load the address!');
            phantom.exit();
        } else {
            window.setTimeout(function () {
                page.render(output);
                phantom.exit();
            }, 200);
        }
    });
}