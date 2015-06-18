 //pedalboards.append({
    //'bundlepath': lilv.lilv_uri_to_path(pedalboard.get_bundle_uri().as_string()),
    //'name': pedalboard.get_name().as_string(),
    //'uri':  pedalboard.get_uri().as_string(),
    //'screenshot': lilv.lilv_uri_to_path(pedalboard.get_value(modpedal.screenshot).get_first().as_string() or ""),
    //'thumbnail':  lilv.lilv_uri_to_path(pedalboard.get_value(modpedal.thumbnail).get_first().as_string() or ""),
    //'width':  pedalboard.get_value(modpedal.width).get_first().as_int(),
    //'height': pedalboard.get_value(modpedal.height).get_first().as_int(),
    //'presets': get_presets(pedalboard)
//})

presetManager = function (node, listURL) {
    this.listURL = listURL;
    this.preset  = false;
    
    this.init = function (node) {
        
        // build elements
        var e = {};
        e.node     = node.addClass("preset-manager");
        e.settings = $("<div class='preset-manager-settings preset-manager-button'></div>").appendTo(node);
        e.entry    = $("<input type=text class=preset-manager-entry>").appendTo(node);
        e.message  = $("<div class=preset-manager-message>").appendTo(node);
        e.load     = $("<div class='preset-manager-load preset-manager-button'>load</div>").appendTo(node);
        e.save     = $("<div class='preset-manager-save preset-manager-button'>save</div>").appendTo(node);
        e.bind     = $("<div class='preset-manager-bind preset-manager-button'>bind</div>").appendTo(node);
        e.clear    = $("<div class='preset-manager-clear preset-manager-button'>clear</div>").appendTo(node);
        e.list     = $("<ul class=preset-manager-list>").appendTo(node);
        
        // add callbacks
        e.node.click(this.nodeClicked.bind(this));
        e.settings.click(this.settingsClicked.bind(this));
        e.entry.click(this.entryClicked.bind(this));
        e.entry.keyup(this.entryKeyup.bind(this));
        e.load.click(this.loadClicked.bind(this));
        e.save.click(this.saveClicked.bind(this));
        e.bind.click(this.bindClicked.bind(this));
        e.clear.click(this.clearClicked.bind(this));
        
        this.buttonConfirm(e.save, this.saveClicked);
        
        // pre-set local vars
        this.elements = e;
        this.active   = false;
        
        this.setPresetTitle("");
        this.loadPresets();
    }
    
    this.loadPresets = function () {
        this.clearPresets();
        this.callBackend(this.listURL, this.addPresets.bind(this));
    }
    
    this.clearPresets = function () {
        this.elements.list.empty();
    }
    
    this.addPresets = function (presets) {
        for (p in presets) {
            var prs = {
                title     : presets[p].metadata.title,
                thumbnail : presets[p].metadata.thumbnail,
                uri       : presets[p].uri
            }
            // tack together
            var e         = {};
            e.node        = $("<li class=preset-manager-preset>").appendTo(this.elements.list);
            e.icon        = $("<img class=preset-manager-preset-icon>").appendTo(e.node);
            e.title       = $("<div class=preset-manager-preset-title>").appendTo(e.node);
            e.description = $("<div class=preset-manager-preset-description>").appendTo(e.node);
            e.load        = $("<div class='preset-manager-button preset-manager-load'>load</div>").appendTo(e.node);
            e.save        = $("<div class='preset-manager-button preset-manager-save'>save</div>").appendTo(e.node);
            e.remove      = $("<div class='preset-manager-button preset-manager-clear'>remove</div>").appendTo(e.node);
            e.bind        = $("<div class='preset-manager-button preset-manager-bind'>bind</div>").appendTo(e.node);
            
            e.title.text(prs.title);
            e.icon.attr("src", prs.thumbnail);
            
            e.node.click((function (prs, that) {
                return (function (e) { this.presetClicked(prs, e); }).bind(that);
            })(prs, this));
            
            e.node.data("preset", prs);
            prs.elements = e;
            
        }
    }
    
    this.presetClicked = function (prs, e) {
        this.preset = prs;
        //this.elements.entry.val(prs.title);
        console.log(prs);
        e.stopPropagation();
    }
    
    this.searchInPresets = function (string) {
        // search for a substring in all preset titles
        for (p in this.presets) {
            if (this.presets.hasOwnProperty(p)) {
                if (p.name.search(string) >= 0) {
                    p.elements.node.slideDown();
                } else {
                    p.elements.node.slideUp();
                    p.elements.title.text(p.name);
                }
            }
        }
    }
    
    this.resetPresets = function () {
        for (p in this.presets) {
            if (this.presets.hasOwnProperty(p)) {
                p.elements.node.slideDown();
                p.elements.title.text(p.name);
            }
        }
    }
    
    this.setPresetTitle = function (string) {
        if (string === "")
            string = "untitled";
        if (string === false)
            string = "";
        this.elements.entry.val(string);
    }
    
    
    this.callBackend = function (url, callback) {
        if (!url) return;
        $.ajax({ 'method': 'GET', 'url': url, 'success': callback, 'dataType': 'json' });
    }
    
    // event handlers
    this.nodeClicked = function (e) {
        
    }
    this.settingsClicked = function (e) {
        e.stopPropagation();
        if (this.active) {
            this.deactivate();
            return;
        }
        $(document).one("click", this.deactivate.bind(this));
        this.elements.node.addClass("active");
        this.active = true;
        this.elements.entry[0].setSelectionRange(0, 9999);
    }
    this.deactivate = function (e) {
        this.elements.node.removeClass("active");
        this.active = false;
        this.elements.entry[0].setSelectionRange(0, 0);
    }
    this.entryClicked = function (e) {
        if (this.active)
            e.stopPropagation();
        else
            e.preventDefault();
    }
    
    this.entryKeyup = function (e) {
        console.log("key");
    }
    
    this.loadClicked = function (e) {
        console.log("load");
    }
    
    this.saveClicked = function (e) {
        console.log("save");
        e.stopPropagation();
    }
    
    this.bindClicked = function (e) {
        console.log("bind");
    }
    
    this.clearClicked = function (e) {
        console.log("clear");
    }
    
    this.buttonConfirm = function (button, callback) {
        var that = this;
        button.click(function (e) {
            var plane = $("<div class=preset-manager-confirm-pane>").click( function () {
                //$(this).remove();
            }).appendTo($(document));
            var confirm = $("<div class=preset-manager-confirm-button>shure?</div>").click(function (e) {
                callback.bind(that)(e);
            }).appendTo(pane).css({width: $(this).outerWidth(), height: $(this).outerHeight(),
                                   top: $(this).position().top, left: $(this).position().left});
        });
        return button;
    }
    
    // bazinga!
    this.init(node);
}
