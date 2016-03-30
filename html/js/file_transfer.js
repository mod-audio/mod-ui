/*
 * Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@moddevices.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
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

function SimpleTransference(from, to, options) {
    this.origin = from.replace(/\/?$/, '/')
    this.destination = to.replace(/\/?$/, '/')
    this.options = $.extend({ from_args: {},
                              to_args: {}
                            }, options)

    this.request = null;
    this.reauthorize = null;

    var self = this

    this.start = function () {
        console.log("[TRANSFERENCE] starting download...")
        var req = $.ajax($.extend({
            type: 'GET',
            url: self.origin,
            success: self.upload,
            dataType: 'binary',
            error: function (resp) {
                if (resp.status == 401 && self.reauthorize != null) {
                    console.log("[TRANSFERENCE] unauthorized, retrying authentication...")
                    self.reauthorize(function (ok, options) {
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
            }
        }, self.options.from_args))
        self.request = req
    }

    this.upload = function (file) {
        console.log("[TRANSFERENCE] download finished, starting upload to " + self.destination)
        var req = $.ajax($.extend({
            method: 'POST',
            url: self.destination,
            data: file,
            contentType: file.type,
            success: self.success,
            processData: false,
            error: function (resp) {
                self.abort(resp.statusText)
            },
            dataType: 'json',
            cache: false
        }, self.options.to_args))
        self.request = req
    }

    this.success = function (resp) {
        console.log("[TRANSFERENCE] upload finished")
        self.reportFinished(resp)
    }

    this.reportInitialStatus = function (upload) {
        var status = {
            complete: true,
            ok: upload.ok,
            percent: 0,
            result: upload.result,
            torrent_id: upload.id
        }
        for (var i in upload.status) {
            if (upload.status[i])
                status.percent += 100 / upload.status.length
            else
                status.complete = false
        }
        self.reportStatus(status)
    }

    this.abort = function (error) {
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

    this.reportStatus = function (status) {}
    this.reportFinished = function () {}
    this.reportError = function (error) {}
}
