export type Demo = 'select' | 'load-tone' | 'load-model' | 'full-api' | 'lan-flow';
export declare enum Gear {
    Amp = "amp",
    AmpCab = "amp-cab",
    /** @deprecated Responses emit `amp-cab` instead; still accepted on input. */
    FullRig = "full-rig",
    Pedal = "pedal",
    Outboard = "outboard",
    Cab = "cab",
    Space = "space",
    Experimental = "experimental",
    /** @deprecated Being retired as a gear; filter with `format: 'ir'` instead. */
    Ir = "ir"
}
export declare enum Format {
    Nam = "nam",
    Ir = "ir",
    AidaX = "aida-x",
    AaSnapshot = "aa-snapshot",
    Proteus = "proteus"
}
export declare enum License {
    T3k = "t3k",
    CcBy = "cc-by",
    CcBySa = "cc-by-sa",
    CcByNc = "cc-by-nc",
    CcByNcSa = "cc-by-nc-sa",
    CcByNd = "cc-by-nd",
    CcByNcNd = "cc-by-nc-nd",
    Cco = "cco"
}
export declare enum Size {
    Standard = "standard",
    Lite = "lite",
    Feather = "feather",
    Nano = "nano",
    Custom = "custom"
}
export declare enum TonesSort {
    BestMatch = "best-match",
    Newest = "newest",
    Oldest = "oldest",
    Trending = "trending",
    DownloadsAllTime = "downloads-all-time"
}
export declare enum UsersSort {
    Tones = "tones",
    Downloads = "downloads",
    Favorites = "favorites",
    Models = "models"
}
export interface EmbeddedUser {
    id: string;
    username: string;
    avatar_url: string | null;
    url: string;
}
export interface User extends EmbeddedUser {
    bio: string | null;
    links: string[] | null;
    created_at: string;
    updated_at: string;
}
export interface PublicUser {
    id: number;
    username: string;
    bio: string | null;
    links: string[] | null;
    avatar_url: string | null;
    downloads_count: number;
    favorites_count: number;
    models_count: number;
    tones_count: number;
    url: string;
}
export interface Make {
    id?: number;
    name: string;
}
export interface Tag {
    id?: number;
    name: string;
}
export interface Tone {
    id: number;
    user_id: string;
    user: EmbeddedUser;
    created_at?: string;
    updated_at?: string;
    title: string;
    description: string | null;
    gear: Gear;
    images: string[] | null;
    is_public: boolean | null;
    links: string[] | null;
    format: Format;
    license: License;
    sizes: Size[];
    makes: Make[];
    tags: Tag[];
    models_count: number;
    downloads_count: number;
    favorites_count: number;
    url: string;
}
/** Neural model architecture version. 'custom' covers user-supplied architectures. */
export type ArchitectureVersion = '1' | '2' | 'custom';
export interface Model {
    id: number;
    created_at: string;
    updated_at: string;
    user_id: string;
    model_url: string;
    name: string;
    size: Size;
    architecture_version: ArchitectureVersion;
    tone_id: number;
}
export interface PaginatedResponse<T> {
    data: T[];
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
}
export interface SearchTonesParams {
    query?: string;
    page?: number;
    pageSize?: number;
    sort?: TonesSort;
    gears?: Gear[];
    /** Model format. Filtering IRs goes here, not through `gears`. */
    format?: Format;
    sizes?: Size[];
    architecture?: number;
    /** Tag names, matched exactly against a tone's `tags`. Multiple values are OR'd. */
    tags?: string[];
    /** Make/model names, matched exactly against a tone's `makes`. OR'd. */
    makes?: string[];
    /** Creator usernames, matched exactly against a tone's `user.username`. OR'd. */
    creators?: string[];
}
export interface ListModelsParams {
    page?: number;
    pageSize?: number;
    architecture?: number;
}
export interface ListCreatedTonesParams {
    page?: number;
    pageSize?: number;
}
export interface ListFavoritedTonesParams {
    page?: number;
    pageSize?: number;
}
export interface ListUsersParams {
    sort?: UsersSort;
    page?: number;
    pageSize?: number;
    query?: string;
}
