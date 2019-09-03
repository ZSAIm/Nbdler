from collections import namedtuple

BlockDumpedData = namedtuple('_BlockDumpedData', 'rel_grid url_id progress')
ProgressDumpedData = namedtuple('_ProgressDumpedData', 'range go_inc done_inc')
HandlerDumpedData = namedtuple('_HandlerDumpedData', 'console url file maxthread buffsize blocksize')
FileDumpedData = namedtuple('_FileDumpedData', 'path name size')
UrlDumpedData = namedtuple('_UrlDumpedData', 'sources')
ConsoleDumpedData = namedtuple('_ConsoleDumpedData', 'block_data acum_time')
SourceUrlDumpedData = namedtuple('_SourceUrlDumpedData',
                                 'url headers cookie proxy max_conn rangef name response')
UrlResponseDumpedData = namedtuple('_UrlResponseDumpedData',
                                   'url headers code length')
ManagerDumpedData = namedtuple('_ManagerDumpedData', 'task_queue max_task')
TaskDumpedData = namedtuple('_TaskDumpedData', 'id filepath opened finished failed fileinfo request child_process')

RequestDumpedData = namedtuple('_RequestDumpedData',
                               'sources filepath resume block_size max_retries max_thread child_process')