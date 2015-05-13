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

$(document).ready(function () {
    $.get('/load_template/plugin.html', function (template) {
        $.ajax({
            method: 'get',
            url: SITEURL + '/effect/list/',
            success: function (effects) {
                for (var i = 0; i < effects.length; i++) {
                    renderEffect(effects[i], template);
                }
            },
            dataType: 'json'
        });
    });
});

function renderEffect(effect, template) {
    var plugin = $(Mustache.render(template, effect));
    plugin.find('.details').each(function () {
        $(this).hide();
    });
    plugin.find('h3').click(function () {
        $(this).next().toggle('fast');
    });
    plugin.find('.details button').click(function () {
        installPlugin(effect,
            plugin.find('.progressbar'),
            $(this));
    });

    $('#browse-effects').append(plugin);
}

function installPlugin(plugin, bar, button) {
    var trans = new SimpleTransference(SITEURL + '/effect/install',
        '/effect/install');

    trans.reportStatus = function (status) {
        bar.progressbar({
            value: status.percent
        });
    };

    trans.reportFinished = function () {
        bar.progressbar({
            value: 100
        });
        button.hide();
    };

    trans.start();

}
