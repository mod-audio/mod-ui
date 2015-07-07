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
    // confirmset: is fired when the confrim message is set. argument is the
    //             new confirm message
    
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
    setConfirm: function (mesg) {
        var self = $(this);
        self.data("button").confirm = mesg != "";
        self.data("button").question = mesg;
        this.trigger("confirmset", [mesg]);
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
            $("body").one("click", function (e) {
                self.removeClass("mod-confirm");
                if (textnodes.length)
                    textnodes[0].nodeValue = options.label;
                e.stopPropagation();
            });
            e.stopImmediatePropagation(true);
            e.preventDefault(true);
            return false;
        }
        self.trigger("action", [e]);
    },
})

JqueryClass("modEditable", {
    // editable has a popout containing a text input. Hitting Enter or
    // clicking the OK button fires the "changed" event with the
    // entered text as argument. Clicking anywhere else
    // hides the poput without any action
    //
    // OPTIONS:
    //
    // text: the text of the element
    // 
    // EVENTS:
    // 
    // changed:  is fired when the user edited the text and hit enter
    //           or clicked the OK button
    
    init: function (options) {
        var self = $(this);
        options = $.extend({
            text: "",
        }, options);
        
        var e = {};
        e.popout = $("<div>");
        e.container = $("<div/>").appendTo(e.popout);
        e.input = $("<input type=text>").appendTo(e.container);
        e.button = $("<div/>").modButton({icon: "ok"}).on("action", function (e) {
            self.modEditable("setText", self.data("elements").input.val());
        }).appendTo(e.container);
        
        e.popout.modPopout({
            content: e.container
        });
        
        self.addClass("mod-editable");
        self.click(self.clicked);
        self.data("options", options);
        self.modEditable("setText", options.text);
        return self;
    },
    setText: function (text) {
        var self = $(this);
        self.data("options").text = text;
        self.text(text);
        self.trigger("changed", [text]);
        return self;
    },
    clicked: function (e) {
        var self = $(this);
        self.data("elements").input.val(self.data("options").text);
        self.modPopout("show");
        $("body").one( function () { self.modPopout("hide"); });
        return self;
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
    // popout:     is fired when the poput is shown
    // popoff:     is fired when the poput disapears
    // anchorset:  is fired when the anchor is set. argument is the
    //             new anchor type
    // contentset: is fired when the content is set. argument is the
    //             new content
    // parentset:  is fired when the parent is set. argument is the
    //             new parent
    
    init: function (options) {
        var self = $(this);
        options = $.extend({
            content: null,
            anchor: MOD_ANCHOR_S,
            parent: null,
            position: true,
            size: true
        }, options);
        
        self.html(Mustache.render(TEMPLATES.popout));
        self.addClass("mod-popout");
        self.addClass("mod-hidden");
        
        var e = {};
        e.anchor = self.find(".mod-popout-anchor");
        e.container = self.find("mod-popout-content");
        
        self.data("options", options);
        self.data("elements", e);
        
        self.modPopout("setAnchor", options.anchor);
        self.modPopout("setContent", options.content);
        self.modPopout("setParent", options.parent);
        return self;
    },
    setAnchor: function (anchor) {
        var self = $(this);
        var p = self.data("elements").popout;
        
        self.removeClass("mod-anchor-n mod-anchor-e mod-anchor-s mod-anchor-w");
        self.removeClass("mod-anchor-ne mod-anchor-se mod-anchor-sw mod-anchor-ne");
        
        switch (anchor) {
            case MOD_ANCHOR_N:
                self.addClass("mod-anchor-n");
                break;
            case MOD_ANCHOR_E:
                self.addClass("mod-anchor-e");
                break;
            case MOD_ANCHOR_S:
                self.addClass("mod-anchor-s");
                break;
            case MOD_ANCHOR_W:
                self.addClass("mod-anchor-w");
                break;
            case MOD_ANCHOR_NE:
                self.addClass("mod-anchor-ne");
                break;
            case MOD_ANCHOR_SE:
                self.addClass("mod-anchor-se");
                break;
            case MOD_ANCHOR_SW:
                self.addClass("mod-anchor-sw");
                break;
            case MOD_ANCHOR_NW:
                self.addClass("mod-anchor-nw");
                break;
        }
        
        self.data("options").anchor = anchor;
        self.trigger("anchorset", [anchor]);
        return self;
    },
    setContent: function (content) {
        var self = $(this);
        self.data("options").content = content;
        self.data("elements").container.append($(content));
        self.trigger("contentset", [content]);
        return self;
    },
    setParent: function (parent) {
        var self = $(this);
        self.data("options").parent = parent;
        //self.data("elements").container.append($(content));
        self.trigger("parentset", [parent]);
        return self;
    },
    show: function () {
        var self = $(this);
        self.removeClass("mod-hidden").addClass("mod-visible");
        var o = self.data("options");
        var p = self.data("elements").popout;
        p.appendTo($("body"));
        switch (o.anchor) {
            default:
            case MOD_ANCHOR_S:
                if (o.size) p.outerWidth(self.outerWidth());
                
                break;
            // TODO: IMPLEMENT ALL ANCHOR POSITIONS AND AUTO POSITIONING
        }
        this.trigger("popout");
        return self;
    },
    hide: function () {
        var self = $(this);
        self.addClass("mod-hidden").removeClass("mod-visible");
        self.data("element").popout.fadeOut();
        self.trigger("popoff");
        return self;
    },
    toggle: function () {
        var self = $(this);
        if (self.hasClass("mod-hidden"))
            self.show();
        else
            self.hide();
        return self;
    }
});

JqueryClass("presetManager", {
    init: function (options) {
        var self = $(this);
        options = $.extend({
            getPresets: function () { return [] },
            preset: "",
        }, options);
        
        self.html(Mustache.render(TEMPLATES.presets));
        var e = {};
        e.entry     = self.find(".preset-manager-entry");
        e.container = self.find(".preset-manager-container");
        e.load      = self.find(".mod-button-load");
        e.save      = self.find(".mod-button-save");
        e.bind      = self.find(".mod-button-bind");
        e.list      = self.find(".mod-list");
        
        e.entry.click(function (e) { self.presetManager("entryClicked", self, e); });
        
        e.entry.keyup(function (e) { self.presetManager("entryKeyup", self, e); });
        
        e.bind.modButton({
            icon: "bind",
            tooltip: "Bind the preset list to a controller",
        }).on("action", function (e) { self.presetManager("bindClicked", self, e); });
        
        e.load.modButton({
            icon: "load",
            label: "load",
            tooltip: "Load the selected preset",
        }).on("action", function (e) { self.presetManager("loadClicked", self, e); });
        
        e.save.modButton({
            icon: "save",
            label: "save",
            tooltip: "Save or overwrite the selected preset",
        }).on("action", function (e) { self.presetManager("saveClicked", self, e); });
        
        self.addClass("preset-manager");
        
        self.data("options", options);
        self.data("elements", e);
        
        self.presetManager("setPresetName", "");
        self.presetManager("setPresets", options.getPresets());
        self.presetManager("setPreset", options.preset);
        return self;
    },
    
    clearPresets: function () {
        var self = $(this);
        self.data("elements").list.empty();
        return self;
    },
    
    addPresets: function (presets) {
        var self = $(this);
        for (p in presets) {
            var li = $("<li>");
            li.presetEntry(presets[p]);
            li.appendTo(self.data("elements").list);
            li.on("clicked", function (e) {
                self.presetManager("setPresetName", $(this).data("options").name);
            });
            li.click( function (e) { e.stopPropagation(); });
        }
        return self;
    },
    
    setPresets: function (presets) {
        var self = $(this);
        self.presetManager("clearPresets");
        self.presetManager("addPresets", presets);
        return self;
    },
    
    resetPresets: function() {
        var self = $(this);
        self.data("elements").list.children().each( function () {
            $(this).css("height", "");
        });
        return self;
    },
    
    setPresetName: function(string) {
        var self = $(this);
        if (string === "")
            string = "untitled";
        if (string === false)
            string = "";
        var entry = self.data("elements").entry;
        entry.val(string);
        entry.attr('size', Math.max(entry.val().length, 1));
        self.presetManager("checkOverwrite");
        return self;
    },
    
    searchInPresets: function(string) {
        // search for a substring in all preset titles
        var self = $(this);
        var o = self.data("options");
        var e = self.data("elements");
        e.list.children().each( function () {
            var t = $(this);
            if (t.data("options").name.toLowerCase().indexOf(string.toLowerCase()) >= 0)
                t.css("height", "");
            else
                t.css("height", 0);
        });
        return self;
    },
    
    setPreset: function (preset) {
        var self = $(this);
        self.data("options").preset = preset;
        self.presetManager("setPresetName", preset);
        self.presetManager("checkOverwrite");
        return self;
    },
    
    getPresetByName: function (name) {
        var self = $(this);
        var e = self.data("elements");
        var a = false;
        e.list.children().each( function () {
            if ($(this).data("options").name == name) {
                a = $(this);
                return false;
            }
        });
        return a;
    },
    
    checkOverwrite: function () {
        var self = $(this);
        var e = self.data("elements");
        if (self.presetManager("getPresetByName", e.entry.val()))
            e.save.modButton("setConfirm", "Sure?");
        else
            e.save.modButton("setConfirm", false);
    },
    
    activate: function() {
        var self = $(this);
        self.addClass("active");
        self.data("elements").entry.focus();
        $("body").one("click", function () { self.presetManager("deactivate"); });
        self.presetManager("resetPresets");
        return self;
    },
    
    deactivate: function() {
        var self = $(this);
        var entry = self.data("elements").entry;
        self.removeClass("active");
        entry.blur();
        self.presetManager("setPresetName", self.data("options").preset);
        return self;
    },
    
    //callBackend: function(url, callback) {
        //if (!url) return;
        //$.ajax({ 'method': 'GET', 'url': url, 'success': callback, 'dataType': 'json' });
    //},
    
    // event handlers
    entryClicked: function(self, e) {
        var self = $(this);
        self.presetManager("activate");
        e.stopPropagation();
        return self;
    },
    
    entryKeyup: function(self, e) {
        var self = $(this);
        var entry = self.data("elements").entry;
        entry.attr('size', Math.max(entry.val().length, 1));
        if (e.keyCode == 13) {
            // return
            
        } else if (e.keyCode == 27) {
            // esc
            self.presetManager("setPresetName", self.data("options").preset);
            self.presetManager("resetPresets");
            self.presetManager("deactivate");
        } else {
            // all other keys
            self.presetManager("searchInPresets", entry.val());
        }
        self.presetManager("checkOverwrite");
        return self;
    },
    
    loadClicked: function(self, e) {
        var self = $(this);
        self.presetManager("deactivate");
        return self;
    },
    
    saveClicked: function(self, e) {
        var self = $(this);
        self.presetManager("deactivate");
        return self;
    },
    
    bindClicked: function(self, e) {
        var self = $(this);
        self.presetManager("deactivate");
        return self;
    },
});


JqueryClass("presetEntry", {
    init: function (options) {
        var self = $(this);
        $.extend({
            name: "untitled",
            bind: "",
            uri:  "",
        }, options);
        
        self.html(Mustache.render(TEMPLATES.preset));
        var e    = {};
        e.name   = self.find(".preset-manager-preset-name");
        e.bind   = self.find(".mod-button-bind");
        e.edit   = self.find(".mod-button-edit");
        e.remove = self.find(".mod-button-remove");
        
        e.bind.modButton({
            icon: "bind",
            tooltip: "Bind the preset to a controller",
        }).on("action",function (e) { self.trigger("bind"); });
        
        e.edit.modButton({
            icon: "edit",
            tooltip: "Edit the presets name",
        }).on("action",function (e) { self.trigger("edit"); });
        
        e.remove.modButton({
            confirm: true,
            question: "",
            icon: "remove",
            tooltip: "Remove this preset",
        }).on("action", function (e) {
                self.trigger("remove");
                self.remove();
        });
        
        e.name.on("click", function () { self.trigger("clicked"); });
        
        self.addClass("mod-list-item");
        
        self.data("options", options);
        self.data("elements", e);
        self.presetEntry("setBind", options.bind);
        self.presetEntry("setName", options.name);
        return self;
    },
    setBind: function (bind) {
        var self = $(this);
        var e = self.data("elements");
        switch (bind) {
            default:
            case MOD_BIND_NONE:
                e.bind.modButton("setIcon", "disconnected");
                break;
            case MOD_BIND_MIDI:
                e.bind.modButton("setIcon", "midi");
                break;
            case MOD_BIND_KNOB:
                e.bind.modButton("setIcon", "knob");
                break;
            case MOD_BIND_FOOTSWITCH:
                e.bind.modButton("setIcon", "footswitch");
                break;
        }
        $(this).data("options").bind = bind;
        return self;
    },
    setName: function (name) {
        var self = $(this);
        self.data("elements").name.text(name);
        self.data("options").name = name;
        return self;
    },
});


$("*").keyup(function (e) {
    if (e.keyCode == 116)
        window.location.reload();
});
