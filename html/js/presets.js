// SOME CONSTANTS
MOD_ANCHOR_N  = "MOD_ANCHOR_N";
MOD_ANCHOR_E  = "MOD_ANCHOR_E";
MOD_ANCHOR_S  = "MOD_ANCHOR_S";
MOD_ANCHOR_W  = "MOD_ANCHOR_W";
MOD_ANCHOR_NE = "MOD_ANCHOR_NE";
MOD_ANCHOR_SE = "MOD_ANCHOR_SE";
MOD_ANCHOR_SW = "MOD_ANCHOR_SW";
MOD_ANCHOR_NW = "MOD_ANCHOR_NW";

JqueryClass("modIcon", {
    // a simple icon wrapper for DIVs
    // more for unification than for simplification
    // the icons colour is determined automaticaly depending on parent
    // elements classes. If any parent has mod-dark or the element
    // itself has mod-light, the icon is drawn as white.
    //
    // OPTIONS:
    // 
    // icons: define the icon type (look into img/icons/icons.css)
    // size:  the icons size, default is 36 pixels
    //
    // EVENTS:
    //
    // iconset: is fired when the icon changes. argument is the
    //          new icon type
    // sizeset: is fired when the size is set. argument is the
    //          new size
    
    init: function (options) {
        options = $.extend({
            icon: "",
            size: 36
        }, options);
        var self = $(this);
        self.data("icon", options);
        self.addClass("mod-icon-" + options.icon);
        self.addClass("mod-icon");
        self.modIcon("setIcon", options.icon);
        self.modIcon("setSize", options.size);
        return self;
    },
    setIcon: function (icon) {
        var self = $(this);
        var i = self.data("icon").icon;
        if (i)
            self.removeClass("mod-icon-" + i);
        if (icon)
            self.addClass("mod-icon-" + icon);
        self.data("icon").icon = icon;
        this.trigger("iconset", [icon]);
        return self;
    },
    setSize: function (size) {
        var self = $(this);
        self.css({ width: size + "px", height: size + "px" });
        self.data("icon").size = size;
        self.trigger("setsize", [size]);
        return self;
    },
});

JqueryClass('modButton', {
    // a button with icon and/or text
    // the fun part is its internal confirmation (e.g. for overwrite
    // or delete actions) - the first click activates confirmation so
    // the button changes its style, icon and label. clicking again
    // fires the "action" event, clicking anywhere else resets
    // confirmation
    //
    // OPTIONS:
    //
    // icon:     if the button has an icon, name the style (empty string
    //           for no label)
    // label;    the buttons label (empty string for no label)
    // tooltip:  tooltip for the button (default HTML title tag)
    // confirm:  bool if confirmation is required before firing event
    // question: the buttons label for confirmation state
    // 
    // EVENTS:
    //
    // action:     is fired when the button is clicked once or twice
    //             depending on the confirm option
    // iconset:    is fired when the icon changes. argument is the
    //             new icon type
    // labelset:   is fired when the label changes. argument is the
    //             new label
    // tooltipset: is fired when the tooltip is set. argument is the
    //             new tooltip
    
    init: function (options) {
        var self = $(this);
        options = $.extend({
            icon: "",
            label: "",
            tooltip: "",
            confirm: false,
            question: "Shure?"
        }, options);
        self.data("button", options);
        self.click(function (e) { self.modButton("clicked", e); });
        if (options.label)
            self.modButton("setLabel", options.label);
        if (options.icon)
            self.modButton("setIcon", options.icon);
        self.modButton("setTooltip", options.tooltip);
        return self;
    },
    setLabel: function (label) {
        var self = $(this);
        self.data("button").label = label;
        self.text(label);
        this.trigger("labelset", [label]);
        return self;
    },
    setIcon: function (icon) {
        var self = $(this);
        if (self.data("icon"))
            self.data("icon").remove();
        if (icon)
            self.data("icon", $("<div>").modIcon({ icon: icon }).prependTo(self));
        else
            self.data("icon", null);
        self.data("button").icon = icon;
        this.trigger("iconset", [icon]);
        return self;
    },
    setTooltip: function (tt) {
        var self = $(this);
        self.attr("title", tt);
        self.trigger("tooltipset", [tt]);
        return self;
    },
    clicked: function (e) {
        var self = $(this);
        var options = self.data("button");
        if (!self.hasClass("mod-confirm") && options.confirm) {
            var textnodes = self.contents().filter(function () { return this.nodeType == 3; });
            if (textnodes.length)
                textnodes[0].nodeValue = options.question;
            self.addClass("mod-confirm");
            $("body").one("click", function () {
                self.removeClass("mod-confirm");
                if (textnodes.length)
                    textnodes[0].nodeValue = options.label;
            });
            e.stopPropagation();
            return;
        }
        self.trigger("action", [e]);
    },
})

JqueryClass("modEditable", {
    // editable has a popout containing a text input. Hitting Enter or
    // clicking the OK button fires the action which is called with
    // entered text and JS event as arguments. Clicking anywhere else
    // hides the poput without any action
    //
    // OPTIONS:
    //
    // title: the text of the element
    // 
    // EVENTS:
    // 
    // changed:  is fired when the user edited the text and hit enter
    //           or clicked the OK button
    init: function (options) {
        var self = $(this);
        options = $.extend({
            title: "",
        }, options);
        self.click(self.clicked);
        self.data("options", options);
        return self;
    },
    setTitle: function (title) {
        $(this).data("options").title = title;
        self.text(title);
        this.trigger("changed", [icon]);
        return self;
    },
    clicked: function (e) {
        
    }
});

JqueryClass("modPopout", {
    // poput is a container showing custom content bound to a specific
    // element. the popout appears directly attached to $(this).
    // 
    // OPTIONS:
    // 
    // content: a JQuery element to display in the popout
    // anchor:  a MOD_ANCHOR_X constant to define the poputs position
    // auto:    a bool determining if the popout is positioned
    //          automatically if it doesn't fit into the screen
    // size:    a bool if the poput is resized to its parents size
    //          depending on its anchor position (width or height)
    //
    // EVENTS:
    //
    // popout: is fired when the poput is shown
    // popoff: is fired when the poput disapears
    
    init: function (options) {
        var self = $(this);
        options = $.extent({
            content: null,
            anchor: MOD_ANCHOR_S,
            auto: true,
            size: true
        }, options);
        var e = {};
        e.popout = $("<div class='mod-popout'/>");
        self.data("options", options);
        self.data("elements", e);
    },
    show: function () {
        var self = $(this);
        var o = self.data("options");
        var p = self.data("elements").popout;
        switch (o.anchor) {
            case default:
            case MOD_ANCHOR_S:
                if (o.size) p.outerWidth(self.outerWidth());
                break;
            // TODO: IMPLEMENT ALL ANCHOR POSITIONS AND AUTO POSITIONING
        this.trigger("popout");
        return self;
    },
    hide: function () {
        var self = $(this);
        self.data("element").popout.fadeOut();
        self.trigger("popoff");
        return self;
    }
});

JqueryClass("presetManager", {
    init: function (options) {
        var self = $(this);
        options = $.extend({
            getPresets: function () { return [] },
        }, options);
        
        self.html(Mustache.render(TEMPLATES.presets));
        var e = {};
        e.entry = self.find(".preset-manager-entry");
        e.load  = self.find(".mod-button-load");
        e.save  = self.find(".mod-button-save");
        e.bind  = self.find(".mod-button-bind");
        e.list  = self.find(".mod-list");
        
        e.entry.click(function (e) { self.presetManager("entryClicked", self, e); });
        e.entry.keyup(function (e) { self.presetManager("entryKeyup", self, e); });
        e.bind.modButton({
            icon: "bind",
            tooltip: "Bind the preset list to a controller",
        }).on("action", function (e) { self.presetManager("loadClicked", self, e); });
        e.load.modButton({
            icon: "load",
            label: "load",
            tooltip: "Load the selected preset",
        }).on("action", function (e) { self.presetManager("bindClicked", self, e); });
        e.save.modButton({
            icon: "save",
            label: "save",
            tooltip: "Save or overwrite the selected preset",
        }).on("action", function (e) { self.presetManager("saveClicked", self, e); });
        
        self.addClass("preset-manager");
        
        self.data("options", options);
        self.data("elements", e);
        
        self.presetManager("setPresetTitle", "");
        self.presetManager("setPresets", options.getPresets());
        return self;
    },
    
    //loadPresets: function () {
        //var self = $(this);
        //self.presetManager("clearPresets");
        //self.presetManager("callBackend", self.data("listURL"),
            //function (o) { self.presetManager("addPresets", o); } 
        //);
    //},
    
    clearPresets: function () {
        var self = $(this);
        self.data("elements").list.empty();
        return self;
    },
    
    addPresets: function (presets) {
        var self = $(this);
        for (p in presets) {
            var li = $("<li>");
            li.presetEntry({
                title: presets[p].name,
                clickPreset: function (e) { },
                bindPreset: function (e) { },
                editPreset: function (e) { },
                removePreset: function (e) { },
            });
            li.appendTo(self.data("elements").list);
        }
        return self;
    },
    
    setPresets: function (presets) {
        var self = $(this);
        self.presetManager("clearPresets");
        self.presetManager("addPresets", presets);
        return self;
    },
    
    presetClicked: function (prs, e) {
        preset = prs;
        //this.elements.entry.val(prs.title);
        console.log(prs);
        e.stopPropagation();
    },
    
    searchInPresets: function(string) {
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
        return self;
    },
    
    resetPresets: function() {
        for (p in this.presets) {
            if (this.presets.hasOwnProperty(p)) {
                p.elements.node.slideDown();
                p.elements.title.text(p.name);
            }
        }
        return self;
    },
    
    setPresetTitle: function(string) {
        if (string === "")
            string = "untitled";
        if (string === false)
            string = "";
        $(this).data("elements").entry.val(string);
        return self;
    },
    
    
    callBackend: function(url, callback) {
        if (!url) return;
        $.ajax({ 'method': 'GET', 'url': url, 'success': callback, 'dataType': 'json' });
    },
    
    // event handlers
    deactivate: function(self, e) {
        
        return self;
    },
    
    entryClicked: function(self, e) {
        console.log("click");
        return self;
    },
    
    entryKeyup: function(self, e) {
        console.log("key");
        return self;
    },
    
    loadClicked: function(self, e) {
        console.log("load");
        return self;
    },
    
    saveClicked: function(self, e) {
        console.log("save");
        return self;
    },
    
    bindClicked: function(self, e) {
        console.log("bind");
        return self;
    },
});


JqueryClass("presetEntry", {
    init: function (options) {
        var self = $(this);
        $.extend({
            title: "untitled",
            bind: "",
            clickPreset: function (e) { },
            bindPreset: function (e) { },
            editPreset: function (e) { },
            removePreset: function (e) { },
        }, options);
        
        self.html(Mustache.render(TEMPLATES.preset));
        var e         = {};
        e.title       = self.find(".preset-manager-preset-entry");
        e.bindstate   = self.find(".preset-manager-preset-bindstate");
        e.bind        = self.find(".mod-button-bind");
        e.edit        = self.find(".mod-button-edit");
        e.remove      = self.find(".mod-button-remove");
        
        self.click(options.clickPreset);
        e.bind.modButton({
            icon: "bind",
            tooltip: "Bind the preset to a controller",
        }).on("action",function (e) { options.bindPreset(e); });
        e.edit.modButton({
            icon: "edit",
            tooltip: "Edit the preset title",
        }).on("action", function (e) { options.bindPreset(e); });
        e.remove.modButton({
            confirm: true,
            question: "",
            icon: "remove",
            tooltip: "Remove this preset",
        }).on("action", function (e) {
                options.removePreset(self, e);
                self.remove();
        });
        
        self.addClass("mod-list-item");
        
        self.data("options", options);
        self.data("elements", e);
        
        self.presetEntry("setBind", options.bind);
        self.presetEntry("setTitle", options.title);
    },
    setBind: function (bind) {
        var self = $(this);
        var e = self.data("elements");
        if (bind) {
            e.bindstate.text(bind);
            self.addClass("bound");
        } else {
            e.bindstate.text("(unlinked)");
            self.removeClass("bound");
        }
        $(this).data("options").bind = bind;
        return self;
    },
    setTitle: function (title) {
        var self = $(this);
        self.data("elements").title.val(title);
        self.data("options").title = title;
        return self;
    },
});
