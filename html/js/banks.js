JqueryClass('bankBox', {
    init: function (options) {
        var self = $(this)

        options = $.extend({
            bankCanvas: self.find('#bank-list .js-canvas'),
            addButton: self.find('#js-add-bank'),
            pedalboardCanvas: self.find('#bank-pedalboards'),
            initMessage: self.find('#bank-init'),
            searchForm: self.find('#bank-pedalboards-search'),
            searchBox: self.find('input[type=search]'),
            resultCanvasUser: self.find('#bank-pedalboards-result .js-user-pedalboards'),
            resultCanvasFactory: self.find('#bank-pedalboards-result .js-factory-pedalboards'),
            bankTitle: self.find('#bank-title'),
            saving: $('#banks-saving'),
            previousBankTitle: null,
            list: function (callback) {
                callback([])
            },
            search: function (local, query, callback) {
                callback([])
            },
            load: function (callback) {
                callback([])
            },
            save: function (data, callback) {
                callback(true)
            },
            copyFactoryPedalboard: function (bundlepath, title, callback) {
                callback({})
            },
            isMainWindow: true,
            windowName: "Banks"
        }, options)

        self.data(options)

        options.pedalboardCanvas.hide()
        options.searchForm.hide()
        options.resultCanvasUser.hide()
        options.resultCanvasFactory.hide()
        options.initMessage.show()
        options.addButton.click(function () {
            self.bankBox('create')
        })

        var searcher = new PedalboardSearcher($.extend({
            searchbox: options.searchBox,
            mode: 'installed',
            skipBroken: true,
            render: function (pedalboard, url) {
                var rendered = self.bankBox('renderPedalboard', pedalboard)
                rendered.draggable({
                    cursor: "grabbing !important",
                    revert: 'invalid',
                    connectToSortable: options.pedalboardCanvas,
                    helper: function () {
                        var helper = rendered.clone().appendTo(self)
                        helper.addClass('mod-banks-drag-item')
                        helper.removeClass('js-pedalboard-item')
                        helper.find('.js-remove').hide()
                        return helper
                    }
                })
                if (pedalboard.factory) {
                    self.data('resultCanvasFactory').append(rendered)
                } else {
                    self.data('resultCanvasUser').append(rendered)
                }
            },
            cleanResults: function () {
                self.data('resultCanvasUser').html('')
                self.data('resultCanvasFactory').html('')
            }
        }, options))

        options.pedalboardCanvas.sortable({
            cursor: "grabbing !important",
            revert: true,
            receive: function (e, ui) {
                // the next update call will be acting on a cloned item, not this one.
                // as such, we need to cache these values and set them on the newly cloned object for the update
                self.droppedBundle = ui.item.data('pedalboardBundle')
                self.droppedTitle = ui.item.data('pedalboardTitle')
                self.isFactoryPedalboard = ui.item.data('isFactoryPedalboard')
                if (self.isFactoryPedalboard) {
                    self.clonedFactoryItem = ui.item.clone()
                }
            },
            update: function (e, ui) {
                if (self.droppedBundle) {
                    // cloned item that got moved into the central area, re-set data attributes
                    ui.item.data('pedalboardBundle', self.droppedBundle)
                    ui.item.data('pedalboardTitle', self.droppedTitle)
                    ui.item.data('isFactoryPedalboard', self.isFactoryPedalboard)

                    // if factory pedalboard was dropped, handle user-data copying
                    if (self.isFactoryPedalboard) {
                        self.data('copyFactoryPedalboard')(self.droppedBundle, self.droppedTitle, function(pb) {
                            ui.item.data('pedalboardBundle', pb.bundlepath)
                            ui.item.data('pedalboardTitle', pb.title)
                            ui.item.data('isFactoryPedalboard', false)
                            ui.item.find('.js-title').text(pb.title)

                            // add the newly copied pedalboard to the user-data canvas area
                            var clone = self.clonedFactoryItem
                            clone.draggable({
                                cursor: "grabbing !important",
                                revert: 'invalid',
                                connectToSortable: options.pedalboardCanvas,
                                helper: function () {
                                    var helper = clone.clone().appendTo(self)
                                    helper.addClass('mod-banks-drag-item')
                                    helper.removeClass('js-pedalboard-item')
                                    helper.find('.js-remove').hide()
                                    return helper
                                }
                            })
                            clone.data('pedalboardBundle', pb.bundlepath)
                            clone.data('pedalboardTitle', pb.title)
                            clone.data('isFactoryPedalboard', false)
                            clone.find('.js-title').text(pb.title)
                            self.data('resultCanvasUser').append(clone)
                            self.clonedFactoryItem = null

                            self.bankBox('save')
                        })
                    }
                }

                ui.item.removeClass('js-pedalboard-item')

                // TODO the code below is repeated. The former click event is not triggered because
                // the element is cloned
                ui.item.find('.js-remove').show().click(function () {
                    ui.item.animate({
                        opacity: 0,
                        height: 0
                    }, function () {
                        ui.item.remove()
                        self.bankBox('save')
                    })
                })

                // if this is a factory pedalboard drop, do not save just yet
                if (!self.isFactoryPedalboard) {
                    self.bankBox('save')
                }

                self.droppedBundle = self.droppedTitle = null
                self.isFactoryPedalboard = false
            },
        })

        options.bankCanvas.sortable({
            handle: '.move',
            update: function () {
                self.bankBox('save')
            }
        })

        options.open = function () {
            searcher.search()
            self.bankBox('load')
            return false
        }

        self.window(options)
    },

    load: function () {
        var self = $(this)
        self.data('loading', true)

        if (self.data('loaded')) {
            self.data('currentBank', null)
            self.data('pedalboardCanvas').html('').hide()
            self.data('searchForm').hide()
            self.data('resultCanvasUser').hide()
            self.data('resultCanvasFactory').hide()
            self.data('bankTitle').hide()
        } else {
            self.data('loaded', true)
        }

        self.data('load')(function (banks) {
            self.data('bankCanvas').html('')
            if (banks.length > 0) {
                var bank, previousBankTitle = self.data('previousBankTitle')
                self.data('currentBank', null)
                self.data('previousBankTitle', null)

                for (var i = 0; i < banks.length; i++) {
                    bank = self.bankBox('renderBank', banks[i], i)
                    if (previousBankTitle == banks[i].title) {
                        self.bankBox('selectBank', bank)
                    }
                }
            }
            self.data('loading', false)
        })
    },

    save: function () {
        var self = $(this)
        var serialized = []
        self.data('bankCanvas').children().each(function () {
            var bank = $(this)
            var pedalboards = (bank.data('selected') ? self.data('pedalboardCanvas') : bank.data('pedalboards'))
            var pedalboardData = []
            pedalboards.children().each(function () {
                var bundle = $(this).data('pedalboardBundle')
                var title = $(this).data('pedalboardTitle')
                if (!bundle) {
                    return
                }
                pedalboardData.push({
                    bundle: bundle,
                    title: title,
                })
            })

            serialized.push({
                title: bank.find('.js-bank-title').text(),
                pedalboards: pedalboardData,
            })
        });
        self.data('saving').html('Auto saving banks...').show()
        self.data('save')(serialized, function (ok) {
            if (ok)
                self.data('saving').html('Auto saving banks... Done!').show()

            else {
                self.data('saving').html('Auto saving banks... Error!').show()
                new Notification('error', 'Error saving banks!')
            }
            if (self.data('savingTimeout')) {
                clearTimeout(self.data('savingTimeout'))
            }
            var timeout = setTimeout(function () {
                self.data('savingTimeout', null)
                self.data('saving').hide()
            }, 500)
            self.data('savingTimeout', timeout)
        })
        // Update displayed indexes
        self.data('pedalboardCanvas').children().each(function (i) {
          var pedalboard = $(this)
          var index = pedalboard.find(".js-index")
          index.html((i+1) + ".&nbsp;")
        })
    },

    create: function () {
        var self = $(this)
        if (self.data('resultCanvasUser').children().length + self.data('resultCanvasFactory').children().length === 0) {
            new Notification('error', 'Before creating banks you must save a pedalboard first.')
            return;
        }
        if (self.data('loading')) {
            return
        }

        var bankData = {
            'title': '',
            'pedalboards': [],
        }
        var bank = self.bankBox('renderBank', bankData)
        self.bankBox('editBank', bank)
        self.bankBox('selectBank', bank)
    },

    renderBank: function (bankData) {
        var self = $(this)
        var bank = $(Mustache.render(TEMPLATES.bank_item, bankData))
        self.data('bankCanvas').append(bank)
        bank.data('selected', false)
        bank.data('pedalboards', $('<div>'))
        bank.data('title', bankData.title)

        var i, pedalboardData, rendered
        for (i = 0; i < bankData.pedalboards.length; i++) {
            rendered = self.bankBox('renderPedalboard', bankData.pedalboards[i], i+1)
            rendered.find('.js-remove').show()
            rendered.appendTo(bank.data('pedalboards'))
        }

        bank.click(function () {
            if (self.data('loading')) {
                self.data('previousBankTitle', bankData.title)
                return
            }
            if (bank.hasClass('selected'))
                self.bankBox('editBank', bank)
            else
                self.bankBox('selectBank', bank)
        })

        bank.find('.js-remove').click(function () {
            if (self.data('loading')) {
                return false
            }
            self.bankBox('removeBank', bank)
            return false
        })

        return bank
    },

    selectBank: function (bank) {
        var self = $(this)
        var pedalboards = bank.data('pedalboards')
        var canvas = self.data('pedalboardCanvas')

        var current = self.data('currentBank')
        if (current) {
            // Save the pedalboards of the current bank
            current.data('pedalboards').append(canvas.children())
            current.data('selected', false)
            // addressing is already saved, every time select is changed
        }

        if (pedalboards.children().length == 0) {
            new Notification('warning', 'This bank is empty - drag pedalboards from the right panel', 5000)
        }

        canvas.append(bank.data('pedalboards').children())

        // Hide initial message
        self.data('initMessage').hide()

        // Show everything else
        canvas.show()
        self.data('searchForm').show()
        self.data('resultCanvasUser').show()
        self.data('resultCanvasFactory').show()

        // Mark this bank as selected
        self.data('currentBank', bank)
        self.data('previousBankTitle', bank.data('title'))
        bank.data('selected', true)
        self.data('bankCanvas').children().removeClass('selected')
        bank.addClass('selected')

        // Replace the title string
        self.data('bankTitle').find('h1').text(bank.data('title') || "Untitled")
        self.data('bankTitle').show()
    },

    editBank: function (bank) {
        var self = $(this)
        var titleBox = bank.find('.js-bank-title')
        if (titleBox.data('editing'))
            return true
        titleBox.data('editing', true)
        var title = titleBox.html()
        titleBox.html('')
        var editBox = $('<input>')
        editBox.val(title)
        editBox.addClass('edit-bank')
        titleBox.append(editBox)
        var finish = function () {
            var title = editBox.val() || 'Untitled'
            titleBox.data('editing', false)
            titleBox.html(title)
            bank.data('title', title)
            self.data('bankTitle').find('h1').text(title)
            self.data('previousBankTitle', title)
            self.bankBox('save')
        }
        editBox.keydown(function (e) {
            if (e.keyCode == 13) {
                finish()
            }
        })
        editBox.blur(finish)
        editBox.focus()
    },

    removeBank: function (bank) {
        var msg = "Deleting bank \""+bank.find('.js-bank-title').html()+"\". Confirm?"
        if (confirm(msg) != true) {
            return;
        }
        var self = $(this)
        var count = bank.data('pedalboards').children().length
        if (count > 1 && !confirm(sprintf('There are %d pedalboards in this bank, are you sure you want to delete it?', count)))
            return
        if (bank.data('selected')) {
            self.data('currentBank', null)
            self.data('previousBankTitle', null)
            self.data('pedalboardCanvas').html('').hide()
            self.data('searchForm').hide()
            self.data('resultCanvasUser').hide()
            self.data('resultCanvasFactory').hide()
            self.data('bankTitle').hide()
        }
        bank.animate({
            opacity: 0,
            height: 0
        }, function () {
            bank.remove();
            self.bankBox('save')
        })
    },

    renderPedalboard: function (pedalboard, index) {
        var self = $(this)

        var metadata = {
            index: index ? (index + ".") : "",
            title: pedalboard.title,
            image: "/img/loading-pedalboard.gif",
        }

        var rendered = $(Mustache.render(TEMPLATES.bank_pedalboard, metadata))

        if (!index) {
            rendered.addClass('js-pedalboard-item')
            rendered.removeClass('clearfix')
        }

        // Assign remove functionality. If removal is not desired (it's a search result),
        // then the remove clickable element will be hidden
        rendered.find('.js-remove').click(function () {
            rendered.animate({
                opacity: 0,
                height: 0
            }, function () {
                rendered.remove()
                self.bankBox('save')
            })
        })

        rendered.data('pedalboardBundle', pedalboard.bundle)
        rendered.data('pedalboardTitle', pedalboard.title)
        rendered.data('isFactoryPedalboard', pedalboard.factory)

        wait_for_pedalboard_screenshot(pedalboard.bundle, pedalboard.version, function (resp) {
            var img = rendered.find('.img img');

            if (resp.ok) {
                img.attr("src", "/pedalboard/image/thumbnail.png?bundlepath="+escape(pedalboard.bundle)+"&tstamp="+resp.ctime+"&v="+pedalboard.version)
                img.css({ top: (img.parent().height() - img.height()) / 2 })
            } else {
                img.attr("src", "/img/icons/broken_image.svg")
                img.css({'width': '100px'})
            }
        })

        return rendered
    }

})
