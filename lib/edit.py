# -*- coding: UTF-8 -*-

__revision__ = '$Id$'

# Copyright © 2005-2011 Vasco Nunes, Piotr Ożarowski

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA

# You may use and distribute this software under the terms of the
# GNU General Public License, version 2 or later

import logging

import gtk

import db
import delete
import gutils

log = logging.getLogger("Griffith")


def change_poster(self):
    """
    changes movie poster image to a custom one
    showing a file chooser dialog to select it
    """
    number = int(self.selected[0])
    if number is None:
        gutils.error(_("You have no movies in your database"), self.widgets['window'])
        return False
    return change_poster_select_file(self, number)


def update_image(self, number, filename):
    imagedata = file(filename, 'rb').read()
    return update_image_from_memory(self, number, imagedata)


def change_poster_select_file(self, number, handler=update_image):
    filename = gutils.file_chooser(_("Select image"),
                                   action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                   buttons=(gtk.STOCK_CANCEL,
                                            gtk.RESPONSE_CANCEL,
                                            gtk.STOCK_OPEN,
                                            gtk.RESPONSE_OK),
                                   name='',
                                   folder=self.locations['desktop'],
                                   picture=True)
    if filename and filename[0]:
        filename = filename[0].decode('UTF-8')
        if handler:
            return handler(self, number, filename)
    return False


def update_image_from_memory(self, number, data):
    session = self.db.Session()
    try:
        loader = gtk.gdk.PixbufLoader()
        loader.write(data, len(data))
        loader.close()
        self.widgets['movie']['picture'].set_from_pixbuf(
            loader.get_pixbuf().scale_simple(100, 140, gtk.gdk.INTERP_BILINEAR))
    except Exception, e:
        log.error(str(e))
        gutils.error(_("Image is not valid."), self.widgets['window'])
        return False

    poster_md5 = gutils.md5sum(data)

    movie = session.query(db.Movie).filter_by(number=number).one()
    if poster_md5 == movie.poster_md5:
        log.debug('same MD5 sum, no need to update poster')
        return False

    old_poster_md5 = movie.poster_md5

    if session.query(db.Poster).filter_by(md5sum=poster_md5).count() == 0:
        poster = db.Poster(md5sum=poster_md5, data=data)
        session.add(poster)

    # update the md5 *after* all other queries (so that UPDATE will not be invoked)
    movie.poster_md5 = poster_md5

    session.add(movie)
    try:
        session.commit()
    except Exception, e:
        session.rollback()
        log.error("cannot add poster to database: %s" % e)
        return False

    if old_poster_md5:
        delete.delete_poster(self, old_poster_md5)

    filename = gutils.get_image_fname(poster_md5, self.db, 's')
    if filename:
        update_tree_thumbnail(self, filename)

    self.widgets['movie']['picture_button'].set_sensitive(True)
    self.widgets['add']['delete_poster'].set_sensitive(True)

    self.update_statusbar(_("Image has been updated"))
    return True


def delete_poster(self, movie_id=None):
    if movie_id is None:
        movie_id = self._movie_id
    session = self.db.Session()
    movie = session.query(db.Movie).filter_by(movie_id=movie_id).first()
    if not movie:
        log.error("Cannot delete unknown movie's poster!")
        return False
    if gutils.question(_("Are you sure you want to delete this poster?"), self.widgets['window']):
        # update in database
        delete.delete_poster(self, movie.poster_md5)
        movie.poster_md5 = None
        session.add(movie)
        try:
            session.commit()
        except Exception, e:
            session.rollback()
            log.error("cannot delete poster: %s" % e)
            return False

        if self._movie_id == movie_id:
            # only if the current selected movie is the same like that one for removing poster
            image_path = gutils.get_defaultimage_fname(self)
            handler = self.widgets['movie']['picture'].set_from_pixbuf(gtk.gdk.pixbuf_new_from_file(image_path))
            gutils.garbage(handler)
            self.widgets['add']['delete_poster'].set_sensitive(False)
            self.widgets['movie']['picture_button'].set_sensitive(False)
        # always refresh the treeview entry
        update_tree_thumbnail(self, gutils.get_defaultthumbnail_fname(self))

        self.update_statusbar(_("Image has been updated"))

        return True
    return False


def update_tree_thumbnail(self, t_image_path):
    self.Image.set_from_file(t_image_path)
    pixbuf = self.Image.get_pixbuf()
    if len(self.selected_iter) > 0 and self.selected_iter[0]:
        self.treemodel.set_value(self.selected_iter[0], 1, pixbuf)
