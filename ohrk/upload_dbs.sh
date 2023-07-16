#!/bin/sh

#lftp -e 'mirror -R -e ohrblog web/pics/ohrblog ; exit' cp
cd databases
lftp -e 'mput -O ohr/ohr_archive/src/databases cp.pickle cpbkup.pickle googleplay.pickle opohr.pickle ss.pickle ss_links.pickle hs.pickle pepsi.pickle; exit' cp
