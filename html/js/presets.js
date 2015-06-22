JqueryClass("presetManager", {
    init: function (options) {
        var self = $(this);
        options = $.extend({
            listURL : "",
            presets: [],
        }, options);
        
        self.html(Mustache.render(TEMPLATES.presets));
        var e = {};
        e.entry = self.find(".preset-manager-entry");
        e.load  = self.find(".preset-manager-button.preset-manager-load");
        e.save  = self.find(".preset-manager-button.preset-manager-save");
        e.bind  = self.find(".preset-manager-button.preset-manager-bind");
        e.list  = self.find(".preset-manager-list");
        
        e.save.confirmButton({action: function (e) { self.presetManager("saveClicked", self, e); }});
        
        e.entry.click(function (e) { self.presetManager("entryClicked", self, e); });
        e.entry.keyup(function (e) { self.presetManager("entryKeyup", self, e); });
        e.load.click(function (e) { self.presetManager("loadClicked", self, e); });
        //e.save.click(function (e) { self.presetManager("saveClicked", self, e); });
        e.bind.click(function (e) { self.presetManager("bindClicked", self, e); });
        
        self.addClass("preset-manager");
        
        self.data("options", options);
        self.data("elements", e);
        
        self.presetManager("setPresetTitle", "");
        self.presetManager("setPresets", options.presets);
        //self.presetManager("loadPresets");
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
                bindPreset: function (self, e) { },
                removePreset: function (self, e) { },
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
            bindPreset: function (self, e) { },
            removePreset: function (self, e) { },
        }, options);
        
        self.html(Mustache.render(TEMPLATES.preset));
        var e         = {};
        e.title       = self.find(".preset-manager-preset-title");
        e.bindstate   = self.find(".preset-manager-preset-bindstate");
        e.bind        = self.find(".preset-manager-button.preset-manager-bind");
        e.remove      = self.find(".preset-manager-button.preset-manager-clear");
        
        self.click(options.clickPreset);
        e.bind.click( function (e) { options.bindPreset(self, e); });
        e.remove.click( function (e) {
            options.removePreset(self, e);
            self.remove();
        });
        
        self.addClass("preset-manager-preset");
        
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
    },
    setTitle: function (title) {
        $(this).data("elements").title.text(title);
    },
});
