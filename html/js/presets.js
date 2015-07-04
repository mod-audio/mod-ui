JqueryClass("modIcon", {
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
        return self;
    },
    setSize: function (size) {
        var self = $(this);
        self.css({ width: size + "px", height: size + "px" });
        self.data("icon").size = size;
        return self;
    },
});

JqueryClass('modButton', {
    init: function (options) {
        var self = $(this);
        options = $.extend({
            icon: "",
            label: "",
            confirm: false,
            action: function (e) { },
            question: "Shure?"
        }, options);
        self.data("button", options);
        self.click(function (e) { self.modButton("clicked", e); });
        if (options.label)
            self.modButton("setLabel", options.label);
        if (options.icon)
            self.modButton("setIcon", options.icon);
        return self;
    },
    setLabel: function (label) {
        var self = $(this);
        self.data("button").label = label;
        self.text(label);
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
        options.action(e);
    },
})

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
            label: "bind",
            action: function (e) { self.presetManager("loadClicked", self, e); }
        });
        e.load.modButton({
            icon: "load",
            label: "load",
            action: function (e) { self.presetManager("bindClicked", self, e); }
        });
        e.save.modButton({
            icon: "save",
            label: "save",
            action: function (e) { self.presetManager("saveClicked", self, e); }
        });
        
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
    },
    
    setPresets: function (presets) {
        var self = $(this);
        self.presetManager("clearPresets");
        self.presetManager("addPresets", presets);
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
    },
    
    resetPresets: function() {
        for (p in this.presets) {
            if (this.presets.hasOwnProperty(p)) {
                p.elements.node.slideDown();
                p.elements.title.text(p.name);
            }
        }
    },
    
    setPresetTitle: function(string) {
        if (string === "")
            string = "untitled";
        if (string === false)
            string = "";
        $(this).data("elements").entry.val(string);
    },
    
    
    callBackend: function(url, callback) {
        if (!url) return;
        $.ajax({ 'method': 'GET', 'url': url, 'success': callback, 'dataType': 'json' });
    },
    
    // event handlers
    deactivate: function(self, e) {
        
    },
    
    entryClicked: function(self, e) {
        console.log("click");
    },
    
    entryKeyup: function(self, e) {
        console.log("key");
    },
    
    loadClicked: function(self, e) {
        console.log("load");
    },
    
    saveClicked: function(self, e) {
        console.log("save");
    },
    
    bindClicked: function(self, e) {
        console.log("bind");
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
            action: function (e) { options.bindPreset(e); }
        });
        e.edit.modButton({
            icon: "edit",
            action: function (e) { options.bindPreset(e); }
        });
        e.remove.modButton({
            confirm: true,
            question: "",
            icon: "remove",
            action: function (e) {
                options.removePreset(self, e);
                self.remove(); }
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
    },
    setTitle: function (title) {
        $(this).data("elements").title.text(title);
        $(this).data("options").title = title;
    },
});
