import argparse
import asyncio
import functools
import logging
import os

import aiofiles
from aiohttp import web


async def archivate(request, delay, path):
    chunk_size = 10485
    archive_hash = request.match_info.get('archive_hash')
    path_to_archive = os.path.join(path, archive_hash)

    if not os.path.exists(path_to_archive):
        reason = 'No archive in {}!'.format(path_to_archive)
        raise web.HTTPNotFound(reason=reason)

    cmd = 'zip -r -{}'.format(path_to_archive)
    process = await asyncio.create_subprocess_exec(
        cmd,
        stdout=asyncio.subprocess.PIPE
    )

    response = web.StreamResponse()
    response.enable_chunked_encoding()
    headers = 'attachment; filename={}.zip'.format(archive_hash)
    content_type = "multipart/form-data"
    response.headers["Content-Type"] = content_type
    response.headers['Content-Disposition'] = headers
    await response.prepare(request)

    try:
        while True:
            chunk = await process.stdout.read(chunk_size)
            if not chunk:
                await response.write_eof()
                break
            await response.write(chunk)
            logging.debug('Sending archive chunk ...')
            if delay:
                await asyncio.sleep(int(delay))
        return response
    except asyncio.CancelledError:
        process.terminate()


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


def get_arguments_parser():
    formatter_class = argparse.ArgumentDefaultsHelpFormatter
    parser = argparse.ArgumentParser(formatter_class=formatter_class)
    parser.add_argument('-p', '--path', type=str,
                        default='test_photos', help='set path to photos')
    parser.add_argument('-c', '--compression', type=int, default=9,
                        help='set compression ratio - min=0, max=9')
    parser.add_argument('-d', '--delay', type=int, default=1,
                        help='set delay of download chunk - min=0, max=9')
    parser.add_argument('-l', '--logs', action='store_true', default=False,
                        help='logging on/off')
    return parser


def main():
    parser = get_arguments_parser()
    args = parser.parse_args()

    if args.logs:
        logging.basicConfig(format=u'%(levelname)-8s [%(asctime)s] %(message)s', level=logging.DEBUG)

    partial_archivate = functools.partial(archivate, delay=args.delay, path=args.path)

    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/test_photos/{archive_hash}/', partial_archivate),
    ])
    web.run_app(app)


if __name__ == '__main__':
    main()
