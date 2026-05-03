#!/bin/bash
# 数据恢复脚本
# 使用方式: ./restore.sh <备份文件名>
# 示例:     ./restore.sh mydb.dump
#           ./restore.sh all_databases.sql

set -e

BACKUP_FILE=$1
CONTAINER_NAME="fit5120_postgres"
PG_USER=${POSTGRES_USER:-postgres}

if [ -z "$BACKUP_FILE" ]; then
    echo "用法: $0 <备份文件名>"
    echo "备份文件需放置在 ./backup/ 目录下"
    exit 1
fi

if [ ! -f "./backup/$BACKUP_FILE" ]; then
    echo "错误: 文件 ./backup/$BACKUP_FILE 不存在"
    exit 1
fi

# 判断文件类型进行不同恢复操作
if [[ "$BACKUP_FILE" == *.sql ]]; then
    echo "检测到 SQL 格式，使用 psql 恢复全库..."
    docker exec -i $CONTAINER_NAME psql -U $PG_USER < ./backup/$BACKUP_FILE
    echo "全库恢复完成！"
elif [[ "$BACKUP_FILE" == *.dump ]]; then
    echo "检测到自定义格式，请输入目标数据库名称："
    read DB_NAME
    echo "正在恢复数据库 $DB_NAME ..."
    docker exec -i $CONTAINER_NAME pg_restore -U $PG_USER -d $DB_NAME --no-owner --no-acl -v < ./backup/$BACKUP_FILE
    echo "数据库 $DB_NAME 恢复完成！"
else
    echo "不支持的文件格式，请使用 .sql 或 .dump 文件"
    exit 1
fi
