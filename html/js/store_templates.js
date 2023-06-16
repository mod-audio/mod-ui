var TEMPLATES = {
    'cloudplugin': '\
<div class="cloud-plugin plugin-container available-plugin js-available-effect" mod-role="cloud-plugin" mod-uri="\{\{uri\}\}">\
    <div class="cloud-plugin-border">\
        <figure class="thumb">  <img src="\{\{thumbnail_href\}\}"></figure>\
        <div class="description">\
            <span class="title">\{\{label\}\}</span>\
            <span class="author">\{\{brand\}\}</span>\
            <hr class="dotted" />\
            <p class="\{\{has_comment\}\}">\{\{comment\}\}<span class="limiter"></span></p>\
        </div>\
        <div class="status-container">\
            \{\{#price\}\}\
            <span class="price-container"><span class="price">\{\{price\}\}</span></span>\
            \{\{/price\}\}\
            \{\{#licensed\}\}\
            <span class="price-container"><span class="licensed"></span></span>\
            \{\{/licensed\}\}\
        </div>\
    </div>\
</div>',
    'cloudplugin_info': '\
<div class="js-close plugin-info plugin-container" mod-uri="\{\{escaped_uri\}\}">\
    <div class="container box">\
        <div class="row-fluid clearfix">\
          <span class="js-close alignright btn btn-mini btn-danger">Close</span>\
          \{\{#price\}\}\
          <div class="description-price-container">\
            <div class="description-price">\{\{price\}\}</div>\
          </div>\
          \{\{/price\}\}\
          \{\{#licensed\}\}\
          <div class="description-price-container">\
            <div class="description-licensed"></div>\
          </div>\
          \{\{/licensed\}\}\
          \{\{#coming\}\}\
          <div class="description-price-container">\
            <div class="description-coming-soon"></div>\
          </div>\
          \{\{/coming\}\}\
            <div class="span10 offset1 clearfix">\
                <figure class="screenshot">\
                    <img src="\{\{screenshot_href\}\}">\
                </figure>\
                <div class="plugin-description">\
                    <header>\
                      <h1>\{\{name\}\}</h1>\
                        <p>\
                            <b>URI:</b> \{\{uri\}\}<br/>\
                            <b>Category:</b> \{\{category\}\}<br/>\
                        </p>\
                        <p>\
                            <b>Author:</b> \{\{author.name\}\}<br/>\
                            <b>Homepage:</b> <a href="\{\{author.homepage\}\}" target="_blank">\{\{author.homepage\}\}</a><br/>\
                        </p>\
                        <p class="version">\
                            <span class="js-latest-version">\
                                Latest Version: <span class="bold">\{\{latest_version\}\}</span><br/>\
                            </span>\
                        </p>\
                    </header>\
                    <p>\{\{comment\}\}</p>\
                    \{\{#pedalboard_href\}\}\
                    <a target="_blank" href="\{\{pedalboard_href\}\}" class="btn btn-info online-button-href">\
                        <span>See it in action</span>\
                    </a>\
                    \{\{/pedalboard_href\}\}\
                    <a target="_blank" href="\{\{plugin_href\}\}" class="btn btn-info online-button-href">\
                        <span>See online</span>\
                    </a>\
                    <div class="plugin-controlports">\
                        <p><strong>CONTROL PORTS:</strong></p>\
                        <table class="plugin-specs table table-bordered">\
                        <tr>\
                            <th>Control</th>\
                            <th>Default</th>\
                            <th>Min</th>\
                            <th>Max</th>\
                        </tr>\
                        \{\{#ports.control.input\}\}\
                        <tr>\
                            <td>\{\{shortName\}\}</td>\
                            <td>\{\{formatted.default\}\}</td>\
                            <td>\{\{formatted.minimum\}\}</td>\
                            <td>\{\{formatted.maximum\}\}</td>\
                        </tr>\
                        \{\{/ports.control.input\}\}\
                        </table>\
                    </div>\
                    <div class="plugin-cvinputs">\
                        <p><strong>CV INPUTS:</strong></p>\
                        <table class="plugin-specs table table-bordered">\
                        <tr>\
                            <th>Port</th>\
                            <th>Default</th>\
                            <th>Min</th>\
                            <th>Max</th>\
                        </tr>\
                        \{\{#ports.cv.input\}\}\
                        <tr>\
                            <td>\{\{shortName\}\}</td>\
                            <td>\{\{formatted.default\}\}</td>\
                            <td>\{\{formatted.minimum\}\}</td>\
                            <td>\{\{formatted.maximum\}\}</td>\
                        </tr>\
                        \{\{/ports.cv.input\}\}\
                        </table>\
                    </div>\
                    <div class="plugin-cvoutputs">\
                        <p><strong>CV OUTPUTS:</strong></p>\
                        <table class="plugin-specs table table-bordered">\
                        <tr>\
                            <th>Port</th>\
                            <th>Default</th>\
                            <th>Min</th>\
                            <th>Max</th>\
                        </tr>\
                        \{\{#ports.cv.output\}\}\
                        <tr>\
                            <td>\{\{shortName\}\}</td>\
                            <td>\{\{formatted.default\}\}</td>\
                            <td>\{\{formatted.minimum\}\}</td>\
                            <td>\{\{formatted.maximum\}\}</td>\
                        </tr>\
                        \{\{/ports.cv.output\}\}\
                        </table>\
                    </div>\
                </div>\
            </div>\
        </div>\
    </div>\
</div>',
    'featuredplugin': '\
<div class="featured" mod-role="cloud-plugin" mod-uri="\{\{uri\}\}" data-priority="\{\{featured.priority\}\}">\
  <div class="box">\
    <div class="inner-box">\
      \{\{#price\}\}\
      <span class="price-container">\
        <span class="price">\{\{price\}\}</span>\
      </span>\
      \{\{/price\}\}\
      \{\{#licensed\}\}\
      <span class="price-container">\
        <span class="licensed"></span>\
      </span>\
      \{\{/licensed\}\}\
      <h3>\{\{label\}\}</h3>\
      <div class="img-container">\
        <img src="\{\{screenshot_href\}\}"/>\
      </div>\
      <p>\{\{featured.headline\}\}</p>\
      <button>Details</button>\
    </div>\
  </div>\
</div>',
    'notification': '\
<section class="notifications notifications-{{type}} alert alert-{{type}}">\
    <button type="button" class="js-close close">&times;</button>\
    <div class="explanation js-message">{{{message}}}</div>\
    <div class="progressbar js-progressbar"></div>\
</section>'
};
