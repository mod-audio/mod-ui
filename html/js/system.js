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

function upgradeSync() {
    var trans = new Transference(SITEURL + '/system/upgrade/sync',
        '/system/upgrade/sync',
        'mod.db.tar.gz');
    trans.reportFinished = function() {
        $.ajax({
            method: 'get',
            url: '/system/upgrade/packages',
            success: upgradePackages,
            dataType: 'json'
        });
    };
    trans.start();
}

function installPkg(pkg) {
    var trans = new Transference(SITEURL + '/system/upgrade/sync',
        '/system/upgrade/sync',
        'mod.db.tar.gz');
    trans.reportFinished = function() {
        $.ajax({
            method: 'get',
            url: '/system/install_pkg/' + pkg,
            success: function(pkgs) { installPackages(pkgs, pkg) },
            dataType: 'json'
        });
    };
    trans.start();
}

function upgradePackages(pkgs) {
    if (pkgs && pkgs.length == 0) {
        return;
    }
    var pkg = pkgs.pop();
    var trans = new Transference(SITEURL + '/system/upgrade/sync',
        '/system/upgrade/package',
        pkg);

    if (pkgs.length > 0) {
        trans.reportFinished = function() {
            upgradePackages(pkgs);
        };
    } else {
        trans.reportFinished = function() {
            $.ajax({
                method: 'get',
                url: '/system/upgrade/do',
                success: function(response) {},
                dataType: 'json'
            });
        };
    }
    trans.start();
}


function installPackages(pkgs, opkg) {
    if (pkgs && pkgs.length == 0) {
        return;
    }
    var pkg = pkgs.pop();
    var trans = new Transference(SITEURL + '/system/upgrade/sync',
        '/system/upgrade/package',
        pkg);

    if (pkgs.length > 0) {
        trans.reportFinished = function() {
            installPackages(pkgs, opkg);
        };
    } else {
        trans.reportFinished = function() {
            $.ajax({
                method: 'get',
                url: '/system/install_pkg/do/' + opkg,
                success: function(response) {},
                dataType: 'json'
            });
        };
    }
    trans.start();
}
