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

function LicenseManager(license_info) {
    var self = this;
    self.licenses = license_info;
    self.index = {};
    for (var i in license_info) {
        self.index[license_info[i].plugin_uri] = true;
    }
}

LicenseManager.prototype.updateLicenses = function(callback) {
    var self = this;
    $.ajax({
        url: '/effect/licenses/list',
        method: 'POST',
        data: JSON.stringify(self.licenses),
        dataType: 'json',
        success: function(missing) {
            var downloadNext = function() {
                if (missing.length == 0)
                    return callback()
                self.downloadLicense(missing.pop(), downloadNext);
            }
            downloadNext();
        },
    });  
}

LicenseManager.prototype.downloadLicense = function(licenseId, callback) {
    $.ajax({
        url: SITEURL + '/licenses/' + licenseId,
        method: 'GET',
        headers: {
            'Authorization' : 'MOD ' + desktop.cloudAccessToken
        },
        success: function(data) {
            $.ajax({
                url: '/effect/licenses/save/' + licenseId,
                data: data,
                method: 'POST',
                success: callback,
                error: function() {
                    new Notification('error', 'Could not save plugin license, please contact support', 8000);
                    callback();
                }
            })
        },
        error: function() {
            new Notification('error', 'Could not get plugin license from Cloud, please contact support', 8000);
            callback();
        }
    });
}

LicenseManager.prototype.licensed = function(uri) {
    return !! this.index[uri];
}
