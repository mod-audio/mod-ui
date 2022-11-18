var SHOPIFY_CLIENT_OPTIONS = {
    domain: 'shop.mod.audio',
    apiKey: 'f98e0beff8656549ce54617c492aa46c',
    appId: '1'
};

var SHOPIFY_PRODUCT_OPTIONS = {
    "product": {
        "variantId": "all",
        "width": "240px",
        "contents": {
            "img": false,
            "imgWithCarousel": false,
            "title": false,
            "variantTitle": false,
            "price": false,
            "description": false,
            "buttonWithQuantity": false,
            "quantity": false
        },
        "styles": {
            "product": {
                "text-align": "left",
                "@media (min-width: 601px)": {
                    "max-width": "100%",
                    "margin-left": "0",
                    "margin-bottom": "50px"
                }
            },
            "button": {
                "background-color": "#d828c3",
                "font-size": "12px",
                "padding-top": "10px",
                "padding-bottom": "10px",
                "padding-left": "15px",
                "padding-right": "15px",
                "margin-left": "5px",
                ":hover": {
                    "background-color": "#c224b0"
                },
                "border-radius": "0px",
                ":focus": {
                    "background-color": "#c224b0"
                }
            },
            "title": {
                "font-size": "26px"
            },
            "price": {
                "font-size": "18px"
            },
            "quantityInput": {
                "font-size": "13px",
                "padding-top": "14.5px",
                "padding-bottom": "14.5px"
            },
            "compareAt": {
                "font-size": "15px"
            }
        }
    },
    "cart": {
        "contents": {
            "button": true
        },
        "styles": {
            "button": {
                "background-color": "#d828c3",
                "font-size": "13px",
                "padding-top": "14.5px",
                "padding-bottom": "14.5px",
                ":hover": {
                    "background-color": "#c224b0"
                },
                "border-radius": "0px",
                ":focus": {
                    "background-color": "#c224b0"
                }
            },
            "footer": {
                "background-color": "#ffffff"
            }
        }
    },
    "modalProduct": {
        "contents": {
            "img": false,
            "imgWithCarousel": true,
            "variantTitle": false,
            "buttonWithQuantity": true,
            "button": false,
            "quantity": false
        },
        "styles": {
            "product": {
                "@media (min-width: 601px)": {
                    "max-width": "100%",
                    "margin-left": "0px",
                    "margin-bottom": "0px"
                }
            },
            "button": {
                "background-color": "#d828c3",
                "font-size": "13px",
                "padding-top": "14.5px",
                "padding-bottom": "14.5px",
                "padding-left": "15px",
                "padding-right": "15px",
                ":hover": {
                    "background-color": "#c224b0"
                },
                "border-radius": "0px",
                ":focus": {
                    "background-color": "#c224b0"
                }
            },
            "quantityInput": {
                "font-size": "13px",
                "padding-top": "14.5px",
                "padding-bottom": "14.5px"
            }
        }
    },
    "toggle": {
        "styles": {
            "toggle": {
                "background-color": "#d828c3",
                ":hover": {
                    "background-color": "#c224b0"
                },
                ":focus": {
                    "background-color": "#c224b0"
                }
            },
            "count": {
                "font-size": "13px"
            }
        }
    },
    "productSet": {
        "styles": {
            "products": {
                "@media (min-width: 601px)": {
                    "margin-left": "-20px"
                }
            }
        }
    }
}
