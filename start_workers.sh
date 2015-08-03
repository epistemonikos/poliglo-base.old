
for i in "$@"
do
case $i in
    -e=*|--exclude=*)
    EXCLUDE_WORKERS="${i#*=}"
    EXCLUDE_WORKERS=`echo $EXCLUDE_WORKERS|tr "," "\n"`
    shift # past argument=value
    ;;
    -w=*|--worker=*)
    ONLY_WORKER="${i#*=}"
    shift # past argument=value
    ;;
    -h|--help)
    HELP=1
    shift # past argument with no value
    ;;
    *)
            # unknown option
    ;;
esac
done

if [[ $HELP == 1 ]]; then
    echo "Usage: $0 [options]";
    echo "";
    echo "[-e=|--exclude=] = Exclude a worker from start (separete them by comma)";
    echo "[-w=|--worker=] = Start one worker";
    echo "[-h|--help] = Show help";
    echo "";
    exit 0;
fi


VALID_EXTENSIONS="(js|py|rb)"

if [[ -z "$exec_paths_py" ]]; then
    exec_paths_py="python"
fi
if [[ -z "$exec_paths_js" ]]; then
    exec_paths_js="node"
fi
if [[ -z "$exec_paths_rb" ]]; then
    exec_paths_rb="ruby"
fi

ALL_POSIBLE_WORKERS=""

for worker_path in ${WORKERS_PATHS//:/ }; do
    abs_worker_path=$(cd $(dirname "$worker_path") && pwd -P)/$(basename "$worker_path");
    posible_workers=`find $abs_worker_path -type f|grep -E "$VALID_EXTENSIONS\$"`
    ALL_POSIBLE_WORKERS="${ALL_POSIBLE_WORKERS}\n${posible_workers}"
done
if [[ -n "$SUPERVISOR_FILE" ]]; then
    supervisor_file="$SUPERVISOR_FILE"
else
    supervisor_file=`mktemp /tmp/supervisor.XXXXXXXXXX`
fi


echo "[unix_http_server]
file=/tmp/supervisor.sock
chmod=0700
[supervisord]
logfile = /var/log/supervisor/supervisord.log
logfile_maxbytes = 50MB
logfile_backups=10
loglevel = info
pidfile = /tmp/supervisord.pid
nodaemon = False
minfds = 1024
minprocs = 200
umask = 022
identifier = supervisor
directory = /var/log/supervisor
nocleanup = true
childlogdir = /var/log/supervisor

[supervisorctl]
serverurl = unix:///tmp/supervisor.sock

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

" > $supervisor_file
WORKERS=`curl -s "$POLIGLO_SERVER_URL/worker_types" | ${exec_paths_py} -c 'import json,sys;workers=json.load(sys.stdin);print " ".join(workers)'`
for worker in $WORKERS; do
    IS_EXCLUDED=`echo "${EXCLUDE_WORKERS}"|grep "^${worker}$"`
    CONFIG_SEPARATOR=","
    if [[ $IS_EXCLUDED ]]; then
        continue
    fi
    if [[ $ONLY_WORKER ]]; then
        if [[ $ONLY_WORKER != $worker ]]; then
            continue
        else
            CONFIG_SEPARATOR=" "
        fi

    fi

    worker_config=`curl -s "$POLIGLO_SERVER_URL/worker_types/$worker/config" | ${exec_paths_py} -c "import json,sys;config=json.load(sys.stdin);print '${CONFIG_SEPARATOR}'.join([str(key)+'=\"'+str(value)+'\"' for key, value in config.iteritems()])"`
    worker_path=`echo -e "${ALL_POSIBLE_WORKERS}" | grep "\/$worker\."|head -n 1`
    extension="${worker_path##*.}"
    exec_variable="exec_paths_$extension"
    exec_path=${!exec_variable}
    if [[ $ONLY_WORKER ]]; then
        RUN_COMMAND="${worker_config} bash -c '${exec_path} ${worker_path}'"
    else
        if [[ -z "$DEPLOY_USER" ]]; then
            DEPLOY_USER="deploy"
        fi
        echo "[program:${worker}]
command=${exec_path} ${worker_path}
environment=${worker_config}
user=${DEPLOY_USER}
" >> $supervisor_file
    fi
done

if [[ -n "$SUPERVISOR_FILE" ]]; then
    echo "${supervisor_file}"
else
    if [[ $ONLY_WORKER ]]; then
        eval "${RUN_COMMAND}"
    else
        supervisord -n -c "${supervisor_file}"
    fi
fi
