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

function LicenseManager() {
    this.index_by_uri = {};
    this.index_by_id = {};
}

// Stores a license in internal index
LicenseManager.prototype.addLicense = function(license) {
    this.index_by_uri[license.plugin_uri] = license
    this.index_by_id[license.id] = license
}


// Gets a list of licenses available, sends it to MOD,
// receives a list of missing license IDs and
// install all missing licenses.
LicenseManager.prototype.addLicenses = function(license_info, callback) {
    var self = this;
    for (var i in license_info)
        self.addLicense(license_info[i]);

    $.ajax({
        url: '/effect/licenses/list',
        method: 'POST',
        data: JSON.stringify(license_info),
        dataType: 'json',
        success: function(missing) {
            self.installLicenses(missing, callback)
        }
    });  
}

// Asynchronously download a list of licenses and saves them to MOD
LicenseManager.prototype.installLicenses = function(missingLicenseIds, callback) {
    var self = this;
    var installedLicenses = missingLicenseIds.length

    if (installedLicenses == 0) {
        callback(installedLicenses)
        return
    }

    var installNext = function() {
        if (missingLicenseIds.length == 0) {
            $.ajax({
                url: '/effect/refresh',
                cache: false,
                dataType: 'json',
                success: function() {
                    callback(installedLicenses)
                }
            });
            return
        }
        self.installLicense(missingLicenseIds.pop(), installNext);
    }
    installNext();
}

// Download single license from cloud and send to MOD
LicenseManager.prototype.installLicense = function(licenseId, callback) {
    var self = this;
    var success =  function() {
        var uri = self.index_by_id[licenseId].plugin_uri;
        desktop.license(uri);
        callback();
    }
    $.ajax({
        url: SITEURL + '/licenses/' + licenseId,
        method: 'GET',
        headers: {
            'Authorization' : 'MOD ' + desktop.cloudAccessToken
        },
        success: function(data) {
            $.ajax({
                url: '/effect/licenses/save/' + licenseId,
                cache: false,
                data: data,
                method: 'POST',
                success: success,
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

// Checks if a plugin is licensed
LicenseManager.prototype.licensed = function(uri) {
    return !! this.index_by_uri[uri];
}
