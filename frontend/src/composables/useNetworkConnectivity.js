import axios from 'axios';
import { computed, reactive } from 'vue';

const emptyNetworkSummary = () => ({ total: 0, ok: 0, warning: 0, error: 0, disabled: 0 });

const summarizeNetworkItems = (items) => {
    const summary = emptyNetworkSummary();
    summary.total = items.length;
    items.forEach((item) => {
        const status = item.status || 'error';
        if (summary[status] !== undefined) summary[status] += 1;
    });
    return summary;
};

const overallNetworkStatus = (summary) => {
    if ((summary.error || 0) > 0) return 'error';
    if ((summary.warning || 0) > 0) return 'warning';
    if ((summary.ok || 0) > 0) return 'ok';
    return 'idle';
};

export function useNetworkConnectivity({ showToast } = {}) {
    const networkConnectivity = reactive({
        visible: false,
        loading: false,
        activeTargetId: '',
        status: 'idle',
        checkedAt: '',
        elapsedMs: 0,
        summary: emptyNetworkSummary(),
        items: [],
        error: '',
    });

    const resetNetworkConnectivity = () => {
        networkConnectivity.status = 'idle';
        networkConnectivity.checkedAt = '';
        networkConnectivity.elapsedMs = 0;
        networkConnectivity.summary = emptyNetworkSummary();
        networkConnectivity.items = [];
        networkConnectivity.error = '';
    };

    const applyNetworkResult = (data, targetId = '') => {
        const items = Array.isArray(data.items) ? data.items : [];
        if (targetId) {
            const nextItem = items[0];
            if (nextItem) {
                const index = networkConnectivity.items.findIndex((item) => item.id === targetId);
                if (index >= 0) {
                    networkConnectivity.items.splice(index, 1, nextItem);
                } else {
                    networkConnectivity.items.push(nextItem);
                }
            }
            networkConnectivity.summary = summarizeNetworkItems(networkConnectivity.items);
            networkConnectivity.status = overallNetworkStatus(networkConnectivity.summary);
        } else {
            networkConnectivity.items = items;
            networkConnectivity.summary = Object.assign(emptyNetworkSummary(), data.summary || summarizeNetworkItems(items));
            networkConnectivity.status = data.status || overallNetworkStatus(networkConnectivity.summary);
        }
        networkConnectivity.checkedAt = data.checked_at || '';
        networkConnectivity.elapsedMs = Number(data.elapsed_ms || 0);
    };

    const runNetworkConnectivityTest = async (targetId = '') => {
        const id = String(targetId || '').trim();
        if (id) {
            networkConnectivity.activeTargetId = id;
        } else {
            resetNetworkConnectivity();
            networkConnectivity.loading = true;
            networkConnectivity.status = 'checking';
        }
        networkConnectivity.error = '';

        try {
            const res = await axios.get('/api/system_health/network', {
                params: id ? { target_id: id } : {},
            });
            applyNetworkResult(res.data || {}, id);
        } catch (e) {
            const message = e.response?.data?.detail || e.message || '网络连通性检测失败';
            networkConnectivity.error = message;
            if (!id) {
                networkConnectivity.status = 'error';
                networkConnectivity.summary = Object.assign(emptyNetworkSummary(), { total: 1, error: 1 });
                networkConnectivity.items = [{
                    id: 'network-api-error',
                    label: '网络检测接口',
                    host: 'ChillPoster API',
                    status: 'error',
                    message,
                    icon: 'fa-solid fa-triangle-exclamation',
                }];
            }
            if (showToast) showToast(`网络检测失败: ${message}`, 'error');
        } finally {
            if (id) {
                networkConnectivity.activeTargetId = '';
            } else {
                networkConnectivity.loading = false;
            }
        }
    };

    const openNetworkConnectivity = () => {
        networkConnectivity.visible = true;
        runNetworkConnectivityTest();
    };

    const closeNetworkConnectivity = () => {
        networkConnectivity.visible = false;
    };

    const networkConnectivityHeadline = computed(() => {
        if (networkConnectivity.loading) return '正在检测连通性...';
        if (networkConnectivity.status === 'error') return '检测完成，有异常';
        if (networkConnectivity.status === 'warning') return '检测完成，有提醒';
        if (networkConnectivity.status === 'ok') return '检测完成';
        return '网络连通性测试';
    });

    const networkConnectivityMetaText = computed(() => {
        if (networkConnectivity.loading) return '正在从 ChillPoster 运行环境访问外部服务';
        if (networkConnectivity.error) return networkConnectivity.error;
        if (!networkConnectivity.checkedAt) return '等待开始';
        const checkedAt = networkConnectivity.checkedAt.replace('T', ' ');
        return `${checkedAt} · ${networkConnectivity.summary.ok}/${networkConnectivity.summary.total} 正常 · ${networkConnectivity.elapsedMs}ms`;
    });

    const getNetworkStatusLabel = (status) => {
        const map = {
            ok: '正常',
            warning: '提醒',
            error: '失败',
            checking: '检测中',
        };
        return map[status] || '未知';
    };

    const getNetworkStatusIcon = (status) => {
        const map = {
            ok: 'fa-solid fa-circle-check',
            warning: 'fa-solid fa-circle-exclamation',
            error: 'fa-solid fa-circle-xmark',
            checking: 'fa-solid fa-spinner fa-spin',
        };
        return map[status] || 'fa-solid fa-circle-question';
    };

    return {
        networkConnectivity,
        networkConnectivityHeadline,
        networkConnectivityMetaText,
        openNetworkConnectivity,
        closeNetworkConnectivity,
        runNetworkConnectivityTest,
        getNetworkStatusLabel,
        getNetworkStatusIcon,
    };
}
