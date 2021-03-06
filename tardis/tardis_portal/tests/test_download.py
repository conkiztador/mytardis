# -*- coding: utf-8 -*-

from os import makedirs
from os.path import abspath, basename, dirname, join, exists
from shutil import rmtree

from django.test import TestCase
from django.test.client import Client

from django.conf import settings
from django.contrib.auth.models import User

from nose.plugins.skip import SkipTest

import filecmp

from tardis.tardis_portal.models import Experiment, Dataset, Dataset_File

from tempfile import NamedTemporaryFile

try:
    from wand.image import Image
    IMAGEMAGICK_AVAILABLE = True
except AttributeError:
    IMAGEMAGICK_AVAILABLE = False

class DownloadTestCase(TestCase):

    def setUp(self):
        # create a test user
        self.user = User.objects.create_user(username='DownloadTestUser',
                                             email='',
                                             password='secret')

        # create a public experiment
        self.experiment1 = Experiment(title='Experiment 1',
                                      created_by=self.user,
                                      public_access=Experiment.PUBLIC_ACCESS_FULL)
        self.experiment1.save()

        # create a non-public experiment
        self.experiment2 = Experiment(title='Experiment 2',
                                      created_by=self.user,
                                      public_access=Experiment.PUBLIC_ACCESS_NONE)
        self.experiment2.save()

        # dataset1 belongs to experiment1
        self.dataset1 = Dataset(experiment=self.experiment1)
        self.dataset1.save()

        # dataset2 belongs to experiment2
        self.dataset2 = Dataset(experiment=self.experiment2)
        self.dataset2.save()

        # absolute path first
        filename1 = 'testfile.txt'
        filename2 = 'testfile.tiff'
        self.dest1 = abspath(join(settings.FILE_STORE_PATH, '%s/%s/'
                                  % (self.experiment1.id,
                                  self.dataset1.id)))
        self.dest2 = abspath(join(settings.FILE_STORE_PATH,
                                '%s/%s/'
                                  % (self.experiment2.id,
                                  self.dataset2.id)))
        if not exists(self.dest1):
            makedirs(self.dest1)
        if not exists(self.dest2):
            makedirs(self.dest2)

        testfile1 = abspath(join(self.dest1, filename1))
        f = open(testfile1, 'w')
        f.write("Hello World!\n")
        f.close()

        testfile2 = abspath(join(self.dest2, filename2))
        if IMAGEMAGICK_AVAILABLE:
            with Image(filename='logo:') as img:
                img.format = 'tiff'
                img.save(filename=testfile2)
        else:
            # Apparently ImageMagick isn't installed...
            # Write a "fake" TIFF file
            f = open(testfile2, 'w')
            f.write("II\x2a\x00")
            f.close()


        self.dataset_file1 = Dataset_File(dataset=self.dataset1,
                                          filename=filename1,
                                          protocol='tardis',
                                          url='tardis://%s' % filename1)
        self.dataset_file1.save()

        self.dataset_file2 = Dataset_File(dataset=self.dataset2,
                                          filename=basename(filename2),
                                          protocol='tardis',
                                          url='tardis://%s' % filename2)
        self.dataset_file2.save()

    def tearDown(self):
        self.user.delete()
        self.experiment1.delete()
        self.experiment2.delete()
        rmtree(self.dest1)
        rmtree(self.dest2)

    def testView(self):
        client = Client()

        # check view of file1
        response = client.get('/datafile/view/%i/' % self.dataset_file1.id)

        self.assertEqual(response['Content-Disposition'],
                         'inline; filename="%s"'
                         % self.dataset_file1.filename)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, 'Hello World!\n')

        # check view of file2
        response = client.get('/datafile/view/%i/' % self.dataset_file2.id)
        # Should be forbidden
        self.assertEqual(response.status_code, 403)

        self.experiment2.public_access=Experiment.PUBLIC_ACCESS_FULL
        self.experiment2.save()
        # check view of file2 again
        response = client.get('/datafile/view/%i/' % self.dataset_file2.id)
        self.assertEqual(response.status_code, 200)

        # The following behaviour relies on ImageMagick
        if IMAGEMAGICK_AVAILABLE:
            # file2 should have a ".png" filename
            self.assertEqual(response['Content-Disposition'],
                             'inline; filename="%s"'
                             % (self.dataset_file2.filename+'.png'))
            # file2 should be a PNG
            self.assertEqual(response['Content-Type'], 'image/png')
            png_signature = "\x89PNG\r\n\x1a\n"
            self.assertEqual(response.content[0:8], png_signature)
        else:
            # file2 should have a ".tiff" filename
            self.assertEqual(response['Content-Disposition'],
                             'inline; filename="%s"'
                             % (self.dataset_file2.filename))
            # file2 should be a TIFF
            self.assertEqual(response['Content-Type'], 'image/tiff')
            tiff_signature = "II\x2a\x00"
            self.assertEqual(response.content[0:4], tiff_signature)


    def testDownload(self):
        client = Client()

        # check download for experiment1
        response = client.get('/download/experiment/%i/zip/' % self.experiment1.id)
        self.assertEqual(response['Content-Disposition'],
                         'attachment; filename="experiment%s-complete.zip"'
                         % self.experiment1.id)
        self.assertEqual(response.status_code, 200)

        # check download of file1
        response = client.get('/download/datafile/%i/' % self.dataset_file1.id)

        self.assertEqual(response['Content-Disposition'],
                         'attachment; filename="%s"'
                         % self.dataset_file1.filename)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, 'Hello World!\n')

        # requesting file2 should be forbidden...
        response = client.get('/download/datafile/%i/' % self.dataset_file2.id)
        self.assertEqual(response.status_code, 403)

        # check dataset1 download
        response = client.post('/download/datafiles/',
                               {'expid': self.experiment1.id,
                                'dataset': [self.dataset1.id],
                                'datafile': []})
        self.assertEqual(response.status_code, 200)

        # check dataset2 download
        response = client.post('/download/datafiles/',
                               {'expid': self.experiment2.id,
                                'dataset': [self.dataset2.id],
                                'datafile': []})
        self.assertEqual(response.status_code, 403)

        # check datafile1 download via POST
        response = client.post('/download/datafiles/',
                               {'expid': self.experiment1.id,
                                'dataset': [],
                                'datafile': [self.dataset_file1.id]})
        self.assertEqual(response.status_code, 200)
        # It should be a zip file (all of which start with "PK")
        self.assertEqual(response.content[0:2], "PK")

        # check datafile2 download via POST
        response = client.post('/download/datafiles/',
                               {'expid': self.experiment2.id,
                                'dataset': [],
                                'datafile': [self.dataset_file2.id]})
        self.assertEqual(response.status_code, 403)

        # Check datafile2 download with second experiment to "metadata only"
        self.experiment2.public_access=Experiment.PUBLIC_ACCESS_METADATA
        self.experiment2.save()
        response = client.get('/download/datafile/%i/' % self.dataset_file2.id)
        # Metadata-only means "no file access"!
        self.assertEqual(response.status_code, 403)

        # Check datafile2 download with second experiment to public
        self.experiment2.public_access=Experiment.PUBLIC_ACCESS_FULL
        self.experiment2.save()
        response = client.get('/download/datafile/%i/' % self.dataset_file2.id)
        self.assertEqual(response.status_code, 200)
        # This should be a TIFF (which often starts with "II\x2a\x00")
        self.assertEqual(response['Content-Type'], 'image/tiff')
        self.assertEqual(response.content[0:4], "II\x2a\x00")


    def testDatasetFile(self):

        # check registered text file for physical file meta information
        df = Dataset_File.objects.get(pk=self.dataset_file1.id)

        try:
            from magic import Magic
            self.assertEqual(df.mimetype, 'text/plain; charset=us-ascii')
        except:
            # XXX Test disabled becuse lib magic can't be loaded
            pass
        self.assertEqual(df.size, str(13))
        self.assertEqual(df.md5sum, '8ddd8be4b179a529afa5f2ffae4b9858')

        # now check a JPG file
        filename = join(abspath(dirname(__file__)),
                        '../static/images/ands-logo-hi-res.jpg')

        dataset = Dataset.objects.get(pk=self.dataset1.id)

        pdf1 = Dataset_File(dataset=dataset,
                            filename=basename(filename),
                            url='file://%s' % filename,
                            protocol='file')
        pdf1.save()
        try:
            from magic import Magic
            self.assertEqual(pdf1.mimetype, 'image/jpeg')
        except:
            # XXX Test disabled becuse lib magic can't be loaded
            pass
        self.assertEqual(pdf1.size, str(14232))
        self.assertEqual(pdf1.md5sum, 'c450d5126ffe3d14643815204daf1bfb')

        # now check that we can override the physical file meta information
        pdf2 = Dataset_File(dataset=dataset,
                            filename=basename(filename),
                            url='file://%s' % filename,
                            protocol='file',
                            mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
                            size=str(0),
                            md5sum='md5sum')
        pdf2.save()
        try:
            from magic import Magic
            self.assertEqual(pdf2.mimetype, 'application/vnd.openxmlformats-officedocument.presentationml.presentation')
        except:
            # XXX Test disabled becuse lib magic can't be loaded
            pass
        self.assertEqual(pdf2.size, str(0))
        self.assertEqual(pdf2.md5sum, 'md5sum')

        pdf2.mimetype = ''
        pdf2.save()

        try:
            from magic import Magic
            self.assertEqual(pdf2.mimetype, 'application/pdf')
        except:
            # XXX Test disabled becuse lib magic can't be loaded
            pass
