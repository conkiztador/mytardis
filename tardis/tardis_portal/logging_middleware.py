# -*- coding: utf-8 -*-

#
# Copyright (c) 2010, Monash e-Research Centre
#   (Monash University, Australia)
# Copyright (c) 2010, VeRSI Consortium
#   (Victorian eResearch Strategic Initiative, Australia)
# All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    *  Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#    *  Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#    *  Neither the name of the VeRSI, the VeRSI Consortium members, nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE REGENTS AND CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import logging


class LoggingMiddleware(object):
    def __init__(self):
        self.logger = logging.getLogger('system.request')

    def process_response(self, request, response):
        try:
            user = request.user
        except:
            user = ''
        ip = request.META['REMOTE_ADDR']
        method = request.method
        status = response.status_code
        extra = {'ip': ip, 'user': user, 'method': method, 'status': status}

        if status < 400:
            self.logger.info(request.path, extra=extra)
        elif status < 500:
            self.logger.warning(request.path, extra=extra)
        else:
            self.logger.error(request.path, extra=extra)

        from django.db import connection
        sql = connection.queries
        if sql:
            extra = {'ip': ip, 'user': user, 'method': 'SQL', 'status': status}
            self.logger.debug(sql, extra=extra)

        return response

    def process_exception(self, request, exception):
        try:
            user = request.user
        except:
            user = ''
        ip = request.META['REMOTE_ADDR']
        method = request.method
        status = 500

        extra = {'ip': ip, 'user': user, 'method': method, 'status': status}
        self.logger.error('%s %s' % (request.path, exception), extra=extra)
        return None
