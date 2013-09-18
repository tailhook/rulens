#!/bin/sh


topology="$1"
addresses="$2"

if [ x"$1" = x ]; then
    echo Usage: ./runtopology.sh topology.yaml addresses.txt > /dev/stderr
fi

killjobs() {
    jobs="$(jobs -p)"
    if [ x"$jobs" = "x" ]; then
        trap - 0
        exit 0
    fi
    kill $jobs
}
trap killjobs 1 2 15 0

mkdir run 2> /dev/null
export NN_NAME_SERVICE=ipc://./run/name_service

python3 -m rulens "$topology" --bind $NN_NAME_SERVICE --verbose &

sleep 1


while read url kind; do
    if [ "${url###}" != "${url}" ]; then
        continue  # a comment
    fi
    topology="${url#topology://}"
    node="$(echo "$url" | grep --only-matching --extended-regexp "hostname=\w+")"
    node="${node#hostname=}"
    case "$kind" in
        device) nanodev --reqrep --topology "$topology" &;;
        NN_REP) nanocat --rep --topology "$topology" -D$node &;;
    esac
done <$addresses

sleep 1

jobs

echo "We have done initialization. You can query the cluster with the following"
echo "NN_NAME_SERVICE=$NN_NAME_SERVICE nanocat --req --topology public -D hello -A -i1"
echo
echo "We will also run a client for you:"
nanocat --req --topology public -D hello -A -i1
