var server = "wss://" + window.location.hostname + window.location.pathname + "janus";

var janus = null;
var streaming = null;
var opaqueId = "streamingtest-"+Janus.randomString(12);

var bitrateTimer = null;
var spinner = null;

var simulcastStarted = false, svcStarted = false;

var selectedStream = null;

$(document).ready(function() {
    // Initialize the library (all console debuggers enabled)
    Janus.init({debug: "all", callback: function() {
        // Use a button to start the demo
        //$('#start').one('click', function() {
        setTimeout(function() {
            $('#start').attr('disabled', true).unbind('click');
            // Make sure the browser supports WebRTC
            if(!Janus.isWebrtcSupported()) {
                alert("No WebRTC support... ");
                return;
            }
            // Create session
            janus = new Janus(
                {
                    server: server,
                    success: function() {
                        // Attach to Streaming plugin
                        janus.attach(
                            {
                                plugin: "janus.plugin.streaming",
                                opaqueId: opaqueId,
                                success: function(pluginHandle) {
                                    streaming = pluginHandle;
                                    Janus.log("Plugin attached! (" + streaming.getPlugin() + ", id=" + streaming.getId() + ")");
                                    // Setup streaming session
                                    updateStreamsList();
                                },
                                error: function(error) {
                                    Janus.error("  -- Error attaching plugin... ", error);
                                    alert("Error attaching plugin... " + error);
                                },
                                iceState: function(state) {
                                    Janus.log("ICE state changed to " + state);
                                },
                                webrtcState: function(on) {
                                    Janus.log("Janus says our WebRTC PeerConnection is " + (on ? "up" : "down") + " now");
                                },
                                onmessage: function(msg, jsep) {
                                    Janus.debug(" ::: Got a message :::", msg);
                                    var result = msg["result"];
                                    if(result) {
                                        if(result["status"]) {
                                            var status = result["status"];
                                            if(status === 'starting')
                                                $('#status').removeClass('hide').text("Starting, please wait...").show();
                                            else if(status === 'started')
                                                $('#status').removeClass('hide').text("Started").show();
                                            else if(status === 'stopped')
                                                stopStream();
                                        } else if(msg["streaming"] === "event") {
                                            // Is simulcast in place?
                                            var substream = result["substream"];
                                            var temporal = result["temporal"];
                                            if((substream !== null && substream !== undefined) || (temporal !== null && temporal !== undefined)) {
                                                if(!simulcastStarted) {
                                                    simulcastStarted = true;
                                                    addSimulcastButtons(temporal !== null && temporal !== undefined);
                                                }
                                                // We just received notice that there's been a switch, update the buttons
                                                updateSimulcastButtons(substream, temporal);
                                            }
                                            // Is VP9/SVC in place?
                                            var spatial = result["spatial_layer"];
                                            temporal = result["temporal_layer"];
                                            if((spatial !== null && spatial !== undefined) || (temporal !== null && temporal !== undefined)) {
                                                if(!svcStarted) {
                                                    svcStarted = true;
                                                    addSvcButtons();
                                                }
                                                // We just received notice that there's been a switch, update the buttons
                                                updateSvcButtons(spatial, temporal);
                                            }
                                        }
                                    } else if(msg["error"]) {
                                        alert(msg["error"]);
                                        stopStream();
                                        return;
                                    }
                                    if(jsep) {
                                        Janus.debug("Handling SDP as well...", jsep);
                                        var stereo = (jsep.sdp.indexOf("stereo=1") !== -1);
                                        // Offer from the plugin, let's answer
                                        streaming.createAnswer(
                                            {
                                                jsep: jsep,
                                                // We want recvonly audio/video and, if negotiated, datachannels
                                                media: { audioSend: false, videoSend: false, data: true },
                                                customizeSdp: function(jsep) {
                                                    if(stereo && jsep.sdp.indexOf("stereo=1") == -1) {
                                                        // Make sure that our offer contains stereo too
                                                        jsep.sdp = jsep.sdp.replace("useinbandfec=1", "useinbandfec=1;stereo=1");
                                                    }
                                                },
                                                success: function(jsep) {
                                                    Janus.debug("Got SDP!", jsep);
                                                    var body = { request: "start" };
                                                    streaming.send({ message: body, jsep: jsep });
                                                    $('#js-audio-stream').html('Disable streaming').removeAttr('disabled').click(stopStream);
                                                },
                                                error: function(error) {
                                                    Janus.error("WebRTC error:", error);
                                                    alert("WebRTC error... " + error.message);
                                                }
                                            });
                                    }
                                },
                                onremotestream: function(stream) {
                                    Janus.debug(" ::: Got a remote stream :::", stream);
                                    var addButtons = false;
                                    if($('#remotevideo').length === 0) {
                                        addButtons = true;
                                        $('#stream').append('<video class="rounded centered hide" id="remotevideo" width="100%" height="100%" playsinline/>');
                                        $('#remotevideo').get(0).volume = 0;
                                        // Show the stream and hide the spinner when we get a playing event
                                        $("#remotevideo").bind("playing", function () {
                                            $('#waitingvideo').remove();
                                            if(this.videoWidth)
                                                $('#remotevideo').removeClass('hide').show();
                                            if(spinner)
                                                spinner.stop();
                                            spinner = null;
                                            var videoTracks = stream.getVideoTracks();
                                            if(!videoTracks || videoTracks.length === 0)
                                                return;
                                            var width = this.videoWidth;
                                            var height = this.videoHeight;
                                            $('#curres').removeClass('hide').text(width+'x'+height).show();
                                            if(Janus.webRTCAdapter.browserDetails.browser === "firefox") {
                                                // Firefox Stable has a bug: width and height are not immediately available after a playing
                                                setTimeout(function() {
                                                    var width = $("#remotevideo").get(0).videoWidth;
                                                    var height = $("#remotevideo").get(0).videoHeight;
                                                    $('#curres').removeClass('hide').text(width+'x'+height).show();
                                                }, 2000);
                                            }
                                        });
                                    }
                                    Janus.attachMediaStream($('#remotevideo').get(0), stream);
                                    $("#remotevideo").get(0).play();
                                    $("#remotevideo").get(0).volume = 1;
                                    var videoTracks = stream.getVideoTracks();
                                    if(!videoTracks || videoTracks.length === 0) {
                                        // No remote video
                                        $('#remotevideo').hide();
                                        if($('#stream .no-video-container').length === 0) {
                                            $('#stream').append(
                                                '<div class="no-video-container">' +
                                                    '<i class="fa fa-video-camera fa-5 no-video-icon"></i>' +
                                                    '<span class="no-video-text">No remote video available</span>' +
                                                '</div>');
                                        }
                                    } else {
                                        $('#stream .no-video-container').remove();
                                        $('#remotevideo').removeClass('hide').show();
                                    }
                                    if(!addButtons)
                                        return;
                                    if(videoTracks && videoTracks.length &&
                                            (Janus.webRTCAdapter.browserDetails.browser === "chrome" ||
                                                Janus.webRTCAdapter.browserDetails.browser === "firefox" ||
                                                Janus.webRTCAdapter.browserDetails.browser === "safari")) {
                                        $('#curbitrate').removeClass('hide').show();
                                        bitrateTimer = setInterval(function() {
                                            // Display updated bitrate, if supported
                                            var bitrate = streaming.getBitrate();
                                            $('#curbitrate').text(bitrate);
                                            // Check if the resolution changed too
                                            var width = $("#remotevideo").get(0).videoWidth;
                                            var height = $("#remotevideo").get(0).videoHeight;
                                            if(width > 0 && height > 0)
                                                $('#curres').removeClass('hide').text(width+'x'+height).show();
                                        }, 1000);
                                    }
                                },
                                ondataopen: function(data) {
                                    Janus.log("The DataChannel is available!");
                                    $('#waitingvideo').remove();
                                    $('#stream').append(
                                        '<input class="form-control" type="text" id="datarecv" disabled></input>'
                                    );
                                    if(spinner)
                                        spinner.stop();
                                    spinner = null;
                                },
                                ondata: function(data) {
                                    Janus.debug("We got data from the DataChannel!", data);
                                    $('#datarecv').val(data);
                                },
                                oncleanup: function() {
                                    Janus.log(" ::: Got a cleanup notification :::");
                                    $('#waitingvideo').remove();
                                    $('#remotevideo').remove();
                                    $('#datarecv').remove();
                                    $('.no-video-container').remove();
                                    $('#bitrate').attr('disabled', true);
                                    $('#bitrateset').html('Bandwidth<span class="caret"></span>');
                                    $('#curbitrate').hide();
                                    if(bitrateTimer)
                                        clearInterval(bitrateTimer);
                                    bitrateTimer = null;
                                    $('#curres').hide();
                                    $('#simulcast').remove();
                                    $('#metadata').empty();
                                    $('#info').addClass('hide').hide();
                                    simulcastStarted = false;
                                }
                            });
                    },
                    error: function(error) {
                        Janus.error(error);
                        alert(error, function() {
                            window.location.reload();
                        });
                    },
                    destroyed: function() {
                        window.location.reload();
                    }
                });
        }, 1);
    }});
});

function updateStreamsList() {
    var body = { request: "list" };
    Janus.debug("Sending message:", body);
    streaming.send({ message: body, success: function(result) {
        if(!result) {
            alert("Got no response to our query for available streams");
            return;
        }
        if(result["list"]) {
            var list = result["list"];
            selectedStream = list[0].id;
            $('#js-audio-stream').attr('disabled', true).unbind('click');
            $('#js-audio-stream').html('Enable streaming').removeAttr('disabled').unbind('click').click(startStream);
            Janus.log("Got a list of available streams");
            Janus.debug(list);
        }
    }});
}

function startStream() {
    Janus.log("Selected video id #" + selectedStream);
    if(!selectedStream) {
        alert("Select a stream from the list");
        return;
    }
    $('#streamset').attr('disabled', true);
    $('#streamslist').attr('disabled', true);
    $('#js-audio-stream').attr('disabled', true).unbind('click');
    var body = { request: "watch", id: parseInt(selectedStream) || selectedStream};
    streaming.send({ message: body });
    // No remote video yet
    $('#stream').append('<video class="rounded centered" id="waitingvideo" width="100%" height="100%" />');
    $('#stream').hide();
    if(spinner == null) {
        var target = document.getElementById('stream');
        spinner = new Spinner({top:100}).spin(target);
    } else {
        spinner.spin();
    }
}

function stopStream() {
    $('#js-audio-stream').attr('disabled', true).unbind('click');
    var body = { request: "stop" };
    streaming.send({ message: body });
    streaming.hangup();
    $('#streamset').removeAttr('disabled');
    $('#streamslist').removeAttr('disabled');
    $('#js-audio-stream').html('Enable streaming').removeAttr('disabled').unbind('click').click(startStream);
    $('#status').empty().hide();
    $('#bitrate').attr('disabled', true);
    $('#bitrateset').html('Bandwidth<span class="caret"></span>');
    $('#curbitrate').hide();
    if(bitrateTimer)
        clearInterval(bitrateTimer);
    bitrateTimer = null;
    $('#curres').empty().hide();
    $('#simulcast').remove();
    simulcastStarted = false;
}

// Helpers to create Simulcast-related UI, if enabled
function addSimulcastButtons(temporal) {
    $('#curres').parent().append(
        '<div id="simulcast" class="btn-group-vertical btn-group-vertical-xs pull-right">' +
        '    <div class"row">' +
        '        <div class="btn-group btn-group-xs" style="width: 100%">' +
        '            <button id="sl-2" type="button" class="btn btn-primary" data-toggle="tooltip" title="Switch to higher quality" style="width: 33%">SL 2</button>' +
        '            <button id="sl-1" type="button" class="btn btn-primary" data-toggle="tooltip" title="Switch to normal quality" style="width: 33%">SL 1</button>' +
        '            <button id="sl-0" type="button" class="btn btn-primary" data-toggle="tooltip" title="Switch to lower quality" style="width: 34%">SL 0</button>' +
        '        </div>' +
        '    </div>' +
        '    <div class"row">' +
        '        <div class="btn-group btn-group-xs hide" style="width: 100%">' +
        '            <button id="tl-2" type="button" class="btn btn-primary" data-toggle="tooltip" title="Cap to temporal layer 2" style="width: 34%">TL 2</button>' +
        '            <button id="tl-1" type="button" class="btn btn-primary" data-toggle="tooltip" title="Cap to temporal layer 1" style="width: 33%">TL 1</button>' +
        '            <button id="tl-0" type="button" class="btn btn-primary" data-toggle="tooltip" title="Cap to temporal layer 0" style="width: 33%">TL 0</button>' +
        '        </div>' +
        '    </div>' +
        '</div>');
    // Enable the simulcast selection buttons
    $('#sl-0').removeClass('btn-primary btn-success').addClass('btn-primary')
        .unbind('click').click(function() {
            toastr.info("Switching simulcast substream, wait for it... (lower quality)", null, {timeOut: 2000});
            if(!$('#sl-2').hasClass('btn-success'))
                $('#sl-2').removeClass('btn-primary btn-info').addClass('btn-primary');
            if(!$('#sl-1').hasClass('btn-success'))
                $('#sl-1').removeClass('btn-primary btn-info').addClass('btn-primary');
            $('#sl-0').removeClass('btn-primary btn-info btn-success').addClass('btn-info');
            streaming.send({ message: { request: "configure", substream: 0 }});
        });
    $('#sl-1').removeClass('btn-primary btn-success').addClass('btn-primary')
        .unbind('click').click(function() {
            toastr.info("Switching simulcast substream, wait for it... (normal quality)", null, {timeOut: 2000});
            if(!$('#sl-2').hasClass('btn-success'))
                $('#sl-2').removeClass('btn-primary btn-info').addClass('btn-primary');
            $('#sl-1').removeClass('btn-primary btn-info btn-success').addClass('btn-info');
            if(!$('#sl-0').hasClass('btn-success'))
                $('#sl-0').removeClass('btn-primary btn-info').addClass('btn-primary');
            streaming.send({ message: { request: "configure", substream: 1 }});
        });
    $('#sl-2').removeClass('btn-primary btn-success').addClass('btn-primary')
        .unbind('click').click(function() {
            toastr.info("Switching simulcast substream, wait for it... (higher quality)", null, {timeOut: 2000});
            $('#sl-2').removeClass('btn-primary btn-info btn-success').addClass('btn-info');
            if(!$('#sl-1').hasClass('btn-success'))
                $('#sl-1').removeClass('btn-primary btn-info').addClass('btn-primary');
            if(!$('#sl-0').hasClass('btn-success'))
                $('#sl-0').removeClass('btn-primary btn-info').addClass('btn-primary');
            streaming.send({ message: { request: "configure", substream: 2 }});
        });
    if(!temporal)    // No temporal layer support
        return;
    $('#tl-0').parent().removeClass('hide');
    $('#tl-0').removeClass('btn-primary btn-success').addClass('btn-primary')
        .unbind('click').click(function() {
            toastr.info("Capping simulcast temporal layer, wait for it... (lowest FPS)", null, {timeOut: 2000});
            if(!$('#tl-2').hasClass('btn-success'))
                $('#tl-2').removeClass('btn-primary btn-info').addClass('btn-primary');
            if(!$('#tl-1').hasClass('btn-success'))
                $('#tl-1').removeClass('btn-primary btn-info').addClass('btn-primary');
            $('#tl-0').removeClass('btn-primary btn-info btn-success').addClass('btn-info');
            streaming.send({ message: { request: "configure", temporal: 0 }});
        });
    $('#tl-1').removeClass('btn-primary btn-success').addClass('btn-primary')
        .unbind('click').click(function() {
            toastr.info("Capping simulcast temporal layer, wait for it... (medium FPS)", null, {timeOut: 2000});
            if(!$('#tl-2').hasClass('btn-success'))
                $('#tl-2').removeClass('btn-primary btn-info').addClass('btn-primary');
            $('#tl-1').removeClass('btn-primary btn-info').addClass('btn-info');
            if(!$('#tl-0').hasClass('btn-success'))
                $('#tl-0').removeClass('btn-primary btn-info').addClass('btn-primary');
            streaming.send({ message: { request: "configure", temporal: 1 }});
        });
    $('#tl-2').removeClass('btn-primary btn-success').addClass('btn-primary')
        .unbind('click').click(function() {
            toastr.info("Capping simulcast temporal layer, wait for it... (highest FPS)", null, {timeOut: 2000});
            $('#tl-2').removeClass('btn-primary btn-info btn-success').addClass('btn-info');
            if(!$('#tl-1').hasClass('btn-success'))
                $('#tl-1').removeClass('btn-primary btn-info').addClass('btn-primary');
            if(!$('#tl-0').hasClass('btn-success'))
                $('#tl-0').removeClass('btn-primary btn-info').addClass('btn-primary');
            streaming.send({ message: { request: "configure", temporal: 2 }});
        });
}

function updateSimulcastButtons(substream, temporal) {
    // Check the substream
    if(substream === 0) {
        toastr.success("Switched simulcast substream! (lower quality)", null, {timeOut: 2000});
        $('#sl-2').removeClass('btn-primary btn-success').addClass('btn-primary');
        $('#sl-1').removeClass('btn-primary btn-success').addClass('btn-primary');
        $('#sl-0').removeClass('btn-primary btn-info btn-success').addClass('btn-success');
    } else if(substream === 1) {
        toastr.success("Switched simulcast substream! (normal quality)", null, {timeOut: 2000});
        $('#sl-2').removeClass('btn-primary btn-success').addClass('btn-primary');
        $('#sl-1').removeClass('btn-primary btn-info btn-success').addClass('btn-success');
        $('#sl-0').removeClass('btn-primary btn-success').addClass('btn-primary');
    } else if(substream === 2) {
        toastr.success("Switched simulcast substream! (higher quality)", null, {timeOut: 2000});
        $('#sl-2').removeClass('btn-primary btn-info btn-success').addClass('btn-success');
        $('#sl-1').removeClass('btn-primary btn-success').addClass('btn-primary');
        $('#sl-0').removeClass('btn-primary btn-success').addClass('btn-primary');
    }
    // Check the temporal layer
    if(temporal === 0) {
        toastr.success("Capped simulcast temporal layer! (lowest FPS)", null, {timeOut: 2000});
        $('#tl-2').removeClass('btn-primary btn-success').addClass('btn-primary');
        $('#tl-1').removeClass('btn-primary btn-success').addClass('btn-primary');
        $('#tl-0').removeClass('btn-primary btn-info btn-success').addClass('btn-success');
    } else if(temporal === 1) {
        toastr.success("Capped simulcast temporal layer! (medium FPS)", null, {timeOut: 2000});
        $('#tl-2').removeClass('btn-primary btn-success').addClass('btn-primary');
        $('#tl-1').removeClass('btn-primary btn-info btn-success').addClass('btn-success');
        $('#tl-0').removeClass('btn-primary btn-success').addClass('btn-primary');
    } else if(temporal === 2) {
        toastr.success("Capped simulcast temporal layer! (highest FPS)", null, {timeOut: 2000});
        $('#tl-2').removeClass('btn-primary btn-info btn-success').addClass('btn-success');
        $('#tl-1').removeClass('btn-primary btn-success').addClass('btn-primary');
        $('#tl-0').removeClass('btn-primary btn-success').addClass('btn-primary');
    }
}

// Helpers to create SVC-related UI for a new viewer
function addSvcButtons() {
    if($('#svc').length > 0)
        return;
    $('#curres').parent().append(
        '<div id="svc" class="btn-group-vertical btn-group-vertical-xs pull-right">' +
        '    <div class"row">' +
        '        <div class="btn-group btn-group-xs" style="width: 100%">' +
        '            <button id="sl-1" type="button" class="btn btn-primary" data-toggle="tooltip" title="Switch to normal resolution" style="width: 50%">SL 1</button>' +
        '            <button id="sl-0" type="button" class="btn btn-primary" data-toggle="tooltip" title="Switch to low resolution" style="width: 50%">SL 0</button>' +
        '        </div>' +
        '    </div>' +
        '    <div class"row">' +
        '        <div class="btn-group btn-group-xs" style="width: 100%">' +
        '            <button id="tl-2" type="button" class="btn btn-primary" data-toggle="tooltip" title="Cap to temporal layer 2 (high FPS)" style="width: 34%">TL 2</button>' +
        '            <button id="tl-1" type="button" class="btn btn-primary" data-toggle="tooltip" title="Cap to temporal layer 1 (medium FPS)" style="width: 33%">TL 1</button>' +
        '            <button id="tl-0" type="button" class="btn btn-primary" data-toggle="tooltip" title="Cap to temporal layer 0 (low FPS)" style="width: 33%">TL 0</button>' +
        '        </div>' +
        '    </div>' +
        '</div>'
    );
    // Enable the VP8 simulcast selection buttons
    $('#sl-0').removeClass('btn-primary btn-success').addClass('btn-primary')
        .unbind('click').click(function() {
            toastr.info("Switching SVC spatial layer, wait for it... (low resolution)", null, {timeOut: 2000});
            if(!$('#sl-1').hasClass('btn-success'))
                $('#sl-1').removeClass('btn-primary btn-info').addClass('btn-primary');
            $('#sl-0').removeClass('btn-primary btn-info btn-success').addClass('btn-info');
            streaming.send({ message: { request: "configure", spatial_layer: 0 }});
        });
    $('#sl-1').removeClass('btn-primary btn-success').addClass('btn-primary')
        .unbind('click').click(function() {
            toastr.info("Switching SVC spatial layer, wait for it... (normal resolution)", null, {timeOut: 2000});
            $('#sl-1').removeClass('btn-primary btn-info btn-success').addClass('btn-info');
            if(!$('#sl-0').hasClass('btn-success'))
                $('#sl-0').removeClass('btn-primary btn-info').addClass('btn-primary');
            streaming.send({ message: { request: "configure", spatial_layer: 1 }});
        });
    $('#tl-0').removeClass('btn-primary btn-success').addClass('btn-primary')
        .unbind('click').click(function() {
            toastr.info("Capping SVC temporal layer, wait for it... (lowest FPS)", null, {timeOut: 2000});
            if(!$('#tl-2').hasClass('btn-success'))
                $('#tl-2').removeClass('btn-primary btn-info').addClass('btn-primary');
            if(!$('#tl-1').hasClass('btn-success'))
                $('#tl-1').removeClass('btn-primary btn-info').addClass('btn-primary');
            $('#tl-0').removeClass('btn-primary btn-info btn-success').addClass('btn-info');
            streaming.send({ message: { request: "configure", temporal_layer: 0 }});
        });
    $('#tl-1').removeClass('btn-primary btn-success').addClass('btn-primary')
        .unbind('click').click(function() {
            toastr.info("Capping SVC temporal layer, wait for it... (medium FPS)", null, {timeOut: 2000});
            if(!$('#tl-2').hasClass('btn-success'))
                $('#tl-2').removeClass('btn-primary btn-info').addClass('btn-primary');
            $('#tl-1').removeClass('btn-primary btn-info').addClass('btn-info');
            if(!$('#tl-0').hasClass('btn-success'))
                $('#tl-0').removeClass('btn-primary btn-info').addClass('btn-primary');
            streaming.send({ message: { request: "configure", temporal_layer: 1 }});
        });
    $('#tl-2').removeClass('btn-primary btn-success').addClass('btn-primary')
        .unbind('click').click(function() {
            toastr.info("Capping SVC temporal layer, wait for it... (highest FPS)", null, {timeOut: 2000});
            $('#tl-2').removeClass('btn-primary btn-info btn-success').addClass('btn-info');
            if(!$('#tl-1').hasClass('btn-success'))
                $('#tl-1').removeClass('btn-primary btn-info').addClass('btn-primary');
            if(!$('#tl-0').hasClass('btn-success'))
                $('#tl-0').removeClass('btn-primary btn-info').addClass('btn-primary');
            streaming.send({ message: { request: "configure", temporal_layer: 2 }});
        });
}

function updateSvcButtons(spatial, temporal) {
    // Check the spatial layer
    if(spatial === 0) {
        toastr.success("Switched SVC spatial layer! (lower resolution)", null, {timeOut: 2000});
        $('#sl-1').removeClass('btn-primary btn-success').addClass('btn-primary');
        $('#sl-0').removeClass('btn-primary btn-info btn-success').addClass('btn-success');
    } else if(spatial === 1) {
        toastr.success("Switched SVC spatial layer! (normal resolution)", null, {timeOut: 2000});
        $('#sl-1').removeClass('btn-primary btn-info btn-success').addClass('btn-success');
        $('#sl-0').removeClass('btn-primary btn-success').addClass('btn-primary');
    }
    // Check the temporal layer
    if(temporal === 0) {
        toastr.success("Capped SVC temporal layer! (lowest FPS)", null, {timeOut: 2000});
        $('#tl-2').removeClass('btn-primary btn-success').addClass('btn-primary');
        $('#tl-1').removeClass('btn-primary btn-success').addClass('btn-primary');
        $('#tl-0').removeClass('btn-primary btn-info btn-success').addClass('btn-success');
    } else if(temporal === 1) {
        toastr.success("Capped SVC temporal layer! (medium FPS)", null, {timeOut: 2000});
        $('#tl-2').removeClass('btn-primary btn-success').addClass('btn-primary');
        $('#tl-1').removeClass('btn-primary btn-info btn-success').addClass('btn-success');
        $('#tl-0').removeClass('btn-primary btn-success').addClass('btn-primary');
    } else if(temporal === 2) {
        toastr.success("Capped SVC temporal layer! (highest FPS)", null, {timeOut: 2000});
        $('#tl-2').removeClass('btn-primary btn-info btn-success').addClass('btn-success');
        $('#tl-1').removeClass('btn-primary btn-success').addClass('btn-primary');
        $('#tl-0').removeClass('btn-primary btn-success').addClass('btn-primary');
    }
}
