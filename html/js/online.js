

// If this is a virtual device, mod-ui might be running inside a path,
// so all calls to / should instead be to /path/
$.ajaxSetup({
    beforeSend: function(jqXHR, settings) {
        var basePath = document.location.pathname.replace(/\/$/, '');
        if (settings.url.match(/^\//)) {
            settings.url = basePath + settings.url;
        }
    }
});
