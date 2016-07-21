/**
 * Wait until the test condition is true or a timeout occurs. Useful for waiting
 * on a server response or for a ui change (fadeIn, etc.) to occur.
 *
 * @param testFx javascript condition that evaluates to a boolean,
 * it can be passed in as a string (e.g.: "1 == 1" or "$('#bar').is(':visible')" or
 * as a callback function.
 * @param onReady what to do when testFx condition is fulfilled,
 * it can be passed in as a string (e.g.: "1 == 1" or "$('#bar').is(':visible')" or
 * as a callback function.
 * @param timeOutMillis the max amount of time to wait. If not specified, 3 sec is used.
 */
function waitFor(testFx, onReady, timeOutMillis) {
    var maxtimeOutMillis = timeOutMillis ? timeOutMillis : 3000, //< Default Max Timout is 3s
        start = new Date().getTime(),
        condition = false,
        interval = setInterval(function() {
            if ( (new Date().getTime() - start < maxtimeOutMillis) && !condition ) {
                // If not time-out yet and condition not yet fulfilled
                condition = (typeof(testFx) === "string" ? eval(testFx) : testFx()); //< defensive code
            } else {
                if(!condition) {
                    console.log("'waitFor()' timed out");
                } else {
                    console.log("'waitFor()' finished in " + (new Date().getTime() - start) + "ms.");
                }

                typeof(onReady) === "string" ? eval(onReady) : onReady(); //< Do what it's supposed to do once the condition is fulfilled
                clearInterval(interval); //< Stop this interval
            }
        }, 250); //< repeat check every 250ms
};

var page = require('webpage').create(),
    system = require('system'),
    address, output, size;

var resources = [];
page.onResourceRequested = function(request) {
    resources[request.id] = request.stage;
};
page.onResourceReceived = function(response) {
    resources[response.id] = response.stage;
};

function waitTwice(step, callback) {
    waitFor(function() {
        // check if all resources are loaded
        for (var i in resources) {
            if (resources[i] != 'end') {
                return false;
            }
        }
        // also check if 'loading pedalboard' message is not visible
        return page.evaluate(function() {
            return !$("#fully-loaded-check").is(":visible");
        });
    }, function() {
        if (step == 1) {
            setTimeout(function() {
                waitTwice(2, callback)
            }, 100)
        } else {
            callback()
        }
    }, 30000)
}

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
            waitTwice(1, function() {
                page.render(output);
                phantom.exit();
            })
        }
    })
}
