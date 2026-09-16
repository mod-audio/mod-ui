// types.ts — TONE3000 API type definitions
export var Gear;
(function (Gear) {
    Gear["Amp"] = "amp";
    Gear["AmpCab"] = "amp-cab";
    /** @deprecated Responses emit `amp-cab` instead; still accepted on input. */
    Gear["FullRig"] = "full-rig";
    Gear["Pedal"] = "pedal";
    Gear["Outboard"] = "outboard";
    Gear["Cab"] = "cab";
    Gear["Space"] = "space";
    Gear["Experimental"] = "experimental";
    /** @deprecated Being retired as a gear; filter with `format: 'ir'` instead. */
    Gear["Ir"] = "ir";
})(Gear || (Gear = {}));
export var Format;
(function (Format) {
    Format["Nam"] = "nam";
    Format["Ir"] = "ir";
    Format["AidaX"] = "aida-x";
    Format["AaSnapshot"] = "aa-snapshot";
    Format["Proteus"] = "proteus";
})(Format || (Format = {}));
export var License;
(function (License) {
    License["T3k"] = "t3k";
    License["CcBy"] = "cc-by";
    License["CcBySa"] = "cc-by-sa";
    License["CcByNc"] = "cc-by-nc";
    License["CcByNcSa"] = "cc-by-nc-sa";
    License["CcByNd"] = "cc-by-nd";
    License["CcByNcNd"] = "cc-by-nc-nd";
    License["Cco"] = "cco";
})(License || (License = {}));
export var Size;
(function (Size) {
    Size["Standard"] = "standard";
    Size["Lite"] = "lite";
    Size["Feather"] = "feather";
    Size["Nano"] = "nano";
    Size["Custom"] = "custom";
})(Size || (Size = {}));
export var TonesSort;
(function (TonesSort) {
    TonesSort["BestMatch"] = "best-match";
    TonesSort["Newest"] = "newest";
    TonesSort["Oldest"] = "oldest";
    TonesSort["Trending"] = "trending";
    TonesSort["DownloadsAllTime"] = "downloads-all-time";
})(TonesSort || (TonesSort = {}));
export var UsersSort;
(function (UsersSort) {
    UsersSort["Tones"] = "tones";
    UsersSort["Downloads"] = "downloads";
    UsersSort["Favorites"] = "favorites";
    UsersSort["Models"] = "models";
})(UsersSort || (UsersSort = {}));
