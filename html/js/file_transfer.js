// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

/*
 * the following function is based on jquery.binarytransport.js
 * made by Henry Algus <henryalgus@gmail.com>
 */
$.ajaxTransport("+binary", function(options, originalOptions, jqXHR){
    // check for conditions and support for blob / arraybuffer response type
    if (window.FormData && ((options.dataType && (options.dataType == 'binary')) || (options.data && ((window.ArrayBuffer && options.data instanceof ArrayBuffer) || (window.Blob && options.data instanceof Blob)))))
    {
        return {
            // create new XMLHttpRequest
            send: function(headers, callback){
                // setup all variables
                var xhr = new XMLHttpRequest(),
                    url = options.url,
                    type = options.type,
                    async = options.async || true,
                    // blob or arraybuffer. Default is blob
                    dataType = options.responseType || "blob",
                    data = options.data || null,
                    username = options.username || null,
                    password = options.password || null;

                xhr.addEventListener('load', function(){
                    var data = {};
                    data[options.dataType] = xhr.response;
                    // make callback and send data
                    callback(xhr.status, xhr.statusText, data, xhr.getAllResponseHeaders());
                });

                xhr.addEventListener('progress', function(event){
                    if (! event.lengthComputable) {
                        return
                    }
                    var percentComplete = event.loaded / event.total;
                    originalOptions.percentageStatus(percentComplete)
                });

                xhr.open(type, url, async, username, password);

                // setup custom headers
                for (var i in headers ) {
                    xhr.setRequestHeader(i, headers[i]);
                }

                xhr.responseType = dataType;
                xhr.send(data);
            },
            abort: function(){
                jqXHR.abort();
            }
        };
    }
});

var isInstallingPackage = false

function SimpleTransference(from, to, options) {
    this.origin = from.replace(/\/?$/, '/')
    this.destination = to.replace(/\/?$/, '/')
    this.options = $.extend({ from_args: {},
                              to_args: {}
                            }, options)

    this.request = null;

    // download reauthorize
    this.reauthorizeDownload = null;
    this.reauthorizedDownload = false;

    // upload reauthorize
    this.reauthorizeUpload = null;
    this.reauthorizedUpload = false;

    var self = this

    this.start = function () {
        isInstallingPackage = true
        self.reauthorizedUpload = false
        var req = $.ajax($.extend({
            type: 'GET',
            url: self.origin,
            success: self.upload,
            dataType: 'binary',
            cache: false,
            global: false,
            error: function (resp) {
                if (resp.status == 401 && self.reauthorizeDownload != null && ! self.reauthorizedDownload) {
                    console.log("[TRANSFERENCE] download unauthorized, retrying authentication...")
                    self.reauthorizedDownload = true
                    self.reauthorizeDownload(function (ok, options) {
                        if (ok) {
                            console.log("[TRANSFERENCE] authentication succeeded")
                            self.options = $.extend(self.options, options)
                            self.start()
                        } else {
                            console.log("[TRANSFERENCE] authentication failed")
                            self.abort(resp.statusText)
                        }
                    })
                    return;
                }
                self.abort(resp.statusText)
            },
            percentageStatus: function (percentage) {
                self.percentageStatus(percentage)
            },
        }, self.options.from_args))
        self.request = req
    }

    this.upload = function (file) {
        self.reauthorizedDownload = false
        var req = $.ajax($.extend({
            method: 'POST',
            url: self.destination,
            data: file,
            contentType: file.type,
            success: self.success,
            processData: false,
            error: function (resp) {
                if (resp.status == 401 && self.reauthorizeUpload != null && ! self.reauthorizedUpload) {
                    console.log("[TRANSFERENCE] upload unauthorized, retrying authentication...")
                    self.reauthorizedUpload = true
                    self.reauthorizeUpload(function (ok, options) {
                        if (ok) {
                            console.log("[TRANSFERENCE] authentication succeeded")
                            self.options = $.extend(self.options, options)
                            self.upload()
                        } else {
                            console.log("[TRANSFERENCE] authentication failed")
                            self.abort(resp.statusText)
                        }
                    })
                    return;
                }
                self.abort(resp.statusText)
            },
            dataType: 'json',
            cache: false,
            global: false,
        }, self.options.to_args))
        self.request = req
    }

    this.percentageStatus = function (percentage) {
        self.reportPercentageStatus(percentage)
    }

    this.success = function (resp) {
        isInstallingPackage = false
        self.reportFinished(resp)
    }

    this.abort = function (error) {
        isInstallingPackage = false
        for (var i in self.requests) {
            self.requests[i].abort()
        }
        self.reportError(error)
    }

    this.endRequest = function (request, xis, ypis) {
        var i = self.requests.indexOf(request)
        if (i >= 0)
            self.requests.splice(i, 1)
    }

    this.release = function () {
        for (attr in this) {
            delete this[attr]
        }
    }

    this.reportPercentageStatus = function (percentage) {}
    this.reportFinished = function () {}
    this.reportError = function (error) {}
}
