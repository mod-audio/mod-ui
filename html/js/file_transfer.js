/*
 * Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@portalmod.com>
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

function Transference(from, to, filename) {
    this.origin = from.replace(/\/?$/, '/')
    this.destination = to.replace(/\/?$/, '/')
    this.file = filename

    this.requests = []

    var self = this

    this.start = function () {
        self.resetStatus()
        var req = $.ajax({
            type: 'GET',
            url: self.origin + self.file,
            success: self.registerUpload,
            dataType: 'json',
            error: function (resp) {
                self.abort(resp.statusText)
            }
        })
        self.requests.push(req)
    }

    this.registerUpload = function (torrent) {
        var req = $.ajax({
            'type': 'POST',
            'url': self.destination,
            'data': JSON.stringify(torrent),
            'success': self.queueChunks,
            'dataType': 'json',
            'error': function (resp) {
                self.abort(resp.statusText)
            }
        })
        self.requests.push(req)

    }

    this.maxConnections = 6 // can be overriden

    this.queueChunks = function (upload) {
        if (!upload.ok)
            return self.reportError(upload.reason)
        self.upload_id = upload.id
        self.queue = []
        self.active = []
        self.errors = {}

        // If download is finished, upload.result will hold result
        self.result = upload.result

        for (var i in upload.status) {
            if (!upload.status[i])
                self.queue.push(i)
            self.errors[i] = 0
        }

        self.reportInitialStatus(upload)
        self.startTime = new Date().getTime()

        var maxConnections = self.maxConnections

        var consume = function () {
            if (self.queue && self.queue.length > 0 && maxConnections > 0) {
                self.downloadNext()
                maxConnections--;
                setTimeout(consume, 0)
            }
        }
        consume()
        self.verifyStatus()
    }

    this.resetStatus = function () {
        self.reportStatus({
            complete: false,
            ok: true,
            percent: 0,
            result: false
        })
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

    this.downloadNext = function () {
        if (self.queue.length == 0)
            return

        var next = self.queue.shift()
        self.active.push(next)
        self.downloadChunk(next)
    }

    this.downloadChunk = function (n) {
        var req = $.ajax({
            'url': self.origin + self.file + '/' + n,
            'success': function (chunk) {
                self.receive(n, chunk)
            },
            'dataType': 'text',
            'complete': self.endRequest,
            'error': function (error) {
                self.chunkError(n, error)
            },
            'cache': false
        })
        self.requests.push(req)
    }

    this.receive = function (n, chunk) {
        self.downloadNext()
        self.uploadChunk(n, chunk)
    }

    this.uploadChunk = function (n, chunk) {
        var req = $.post(self.destination + self.upload_id + '/' + n,
            chunk,
            function (status) {
                self.finishChunk(n, status)
            },
            'json')
        self.requests.push(req)
    }

    this.finishChunk = function (n, status) {
        self.reportStatus(status)

        if (self.active.indexOf(n) >= 0)
            self.active.splice(self.active.indexOf(n), 1)

        // If download is finished, status.result will hold result
        self.result = status.result

        self.verifyStatus()
    }

    this.verifyStatus = function () {
        if (self.active.length == 0 && self.queue.length == 0) {
            var delay = (new Date().getTime() - self.startTime) / 1000
            if (delay > 0 && false) // change to true to log download time
                console.log(self.maxConnections + '\t' +
                self.file.replace(/\D/g, '') + '\t' +
                delay + '\t')
            self.finish()
        }
    }

    this.finish = function () {
        self.reportFinished(self.result)
        self.release()
    }

    this.chunkError = function (n, error) {
        self.errors[n]++
            if (self.errors[n] > 3)
                return self.abort(error)

        self.queue.push(n)
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