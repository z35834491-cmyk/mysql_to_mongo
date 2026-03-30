"""
Deterministic on-host / cluster evidence steps. Platform does not execute these;
operators run them and paste output back for the final LLM pass.
"""


def build_checklist(alert_name: str, labels: dict) -> list:
    """
    Returns list of dicts: id, title, purpose, command, capture_hint
    """
    name = (alert_name or "").upper()
    instance = labels.get("instance") or labels.get("node") or labels.get("nodename") or "<节点>"
    namespace = labels.get("namespace") or ""
    pod = labels.get("pod") or ""

    disk_steps = [
        {
            "id": "disk_df_h",
            "title": "整体磁盘与挂载点用量",
            "purpose": "确认哪个挂载点爆满、是否为临时盘或数据盘。",
            "command": "df -hT",
            "capture_hint": "粘贴完整输出；关注 Use% 接近 100% 的行。",
        },
        {
            "id": "disk_du_root",
            "title": "根分区一级目录占用（粗定位大目录）",
            "purpose": "快速找出 /var、/opt、/home 等是否异常膨胀。",
            "command": "sudo du -xh / --max-depth=1 2>/dev/null | sort -h",
            "capture_hint": "若权限不足，在可疑目录下改用 du -sh *。",
        },
        {
            "id": "disk_inodes",
            "title": "inode 是否耗尽",
            "purpose": "磁盘未满但无法创建文件时常见。",
            "command": "df -hi",
            "capture_hint": "粘贴 IUse 或 IFree 相关列。",
        },
        {
            "id": "disk_lsof_deleted",
            "title": "已删除但仍占空间的文件",
            "purpose": "日志被 rm 但进程仍持有 fd 会导致空间不释放。",
            "command": "sudo lsof +L1 2>/dev/null | head -100",
            "capture_hint": "关注 (deleted) 且 SIZE 很大的条目。",
        },
        {
            "id": "disk_journal",
            "title": "systemd journal 占用",
            "purpose": "部分节点 journal 无限增长占满 /var。",
            "command": "journalctl --disk-usage 2>/dev/null || echo '无 journalctl 或权限不足'",
            "capture_hint": "粘贴 journal 报告的磁盘用量。",
        },
    ]

    cpu_steps = [
        {
            "id": "cpu_top",
            "title": "CPU 热点进程",
            "purpose": "定位占用 CPU 的 PID 与命令行。",
            "command": "top -b -n 1 | head -40",
            "capture_hint": "或 `ps aux --sort=-%cpu | head -20`。",
        },
        {
            "id": "cpu_load",
            "title": "负载与运行队列",
            "purpose": "区分 CPU 饱和 vs IO wait。",
            "command": "uptime && vmstat 1 5",
            "capture_hint": "粘贴 uptime 与 vmstat 后几行。",
        },
    ]

    mem_steps = [
        {
            "id": "mem_free",
            "title": "内存与交换区概览",
            "purpose": "确认是否 OOM 前兆、cache 是否正常。",
            "command": "free -h && swapon --show",
            "capture_hint": "关注 available / swap used。",
        },
        {
            "id": "mem_top",
            "title": "内存占用 Top 进程",
            "purpose": "定位 RSS 异常的进程。",
            "command": "ps aux --sort=-%mem | head -25",
            "capture_hint": "粘贴表头与前几行。",
        },
    ]

    k8s_pod_steps = []
    if namespace and pod:
        k8s_pod_steps = [
            {
                "id": "k8s_describe_pod",
                "title": "Pod 事件与状态",
                "purpose": "CrashLoop、镜像拉取失败、探针失败等。",
                "command": f"kubectl describe pod -n {namespace} {pod}",
                "capture_hint": "重点粘贴 Events 段。",
            },
            {
                "id": "k8s_logs_pod",
                "title": "Pod 当前日志",
                "purpose": "应用层错误栈或重启前日志。",
                "command": f"kubectl logs -n {namespace} {pod} --tail=200",
                "capture_hint": "若多容器，加 -c <container>。",
            },
        ]

    intro = {
        "id": "context_where",
        "title": "确认执行环境",
        "purpose": f"在告警关联节点上执行（当前 labels 中 instance/node 约为: {instance}）。",
        "command": "hostname && date -u",
        "capture_hint": "证明命令在目标机器上执行。",
    }

    if "DISK" in name or "IO" in name or "SPACE" in name or "VOLUME" in name:
        return [intro] + disk_steps + k8s_pod_steps

    if "CPU" in name or "LOAD" in name:
        return [intro] + cpu_steps + k8s_pod_steps

    if "MEM" in name or "MEMORY" in name or "OOM" in name:
        return [intro] + mem_steps + k8s_pod_steps

    generic = [
        intro,
        {
            "id": "gen_df",
            "title": "磁盘概览",
            "purpose": "排除磁盘满导致的服务异常。",
            "command": "df -h",
            "capture_hint": "完整输出。",
        },
        {
            "id": "gen_dmesg",
            "title": "内核近期错误",
            "purpose": "硬件、OOM killer、文件系统错误线索。",
            "command": "dmesg -T | tail -80",
            "capture_hint": "或 journalctl -k -n 80。",
        },
    ]
    return generic + k8s_pod_steps
