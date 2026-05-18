import axios from 'axios';
import { computed, onUnmounted, reactive } from 'vue';

const emptySummary = () => ({ total: 0, ok: 0, warning: 0, error: 0, disabled: 0 });

export function useSystemHealth({ showToast } = {}) {
    const systemHealth = reactive({
        visible: false,
        loading: false,
        progress: 0,
        status: 'idle',
        checkedAt: '',
        elapsedMs: 0,
        summary: emptySummary(),
        items: [],
        error: '',
    });

    let progressTimer = null;

    const clearProgressTimer = () => {
        if (progressTimer) {
            clearInterval(progressTimer);
            progressTimer = null;
        }
    };

    const resetSystemHealth = () => {
        systemHealth.progress = 0;
        systemHealth.status = 'idle';
        systemHealth.checkedAt = '';
        systemHealth.elapsedMs = 0;
        systemHealth.summary = emptySummary();
        systemHealth.items = [];
        systemHealth.error = '';
    };

    const animateSystemHealthProgress = () => {
        clearProgressTimer();
        progressTimer = setInterval(() => {
            if (!systemHealth.loading) return;
            const next = systemHealth.progress + Math.max(1, Math.round((92 - systemHealth.progress) * 0.12));
            systemHealth.progress = Math.min(92, next);
        }, 180);
    };

    const runSystemHealthCheck = async () => {
        clearProgressTimer();
        resetSystemHealth();
        systemHealth.loading = true;
        systemHealth.status = 'checking';
        systemHealth.progress = 8;
        animateSystemHealthProgress();

        try {
            const res = await axios.get('/api/system_health');
            const data = res.data || {};
            systemHealth.summary = Object.assign(emptySummary(), data.summary || {});
            systemHealth.items = Array.isArray(data.items) ? data.items : [];
            systemHealth.checkedAt = data.checked_at || '';
            systemHealth.elapsedMs = Number(data.elapsed_ms || 0);
            systemHealth.status = data.status || (systemHealth.summary.error > 0 ? 'error' : 'ok');
            systemHealth.progress = 100;
        } catch (e) {
            const message = e.response?.data?.detail || e.message || '健康检查失败';
            systemHealth.error = message;
            systemHealth.status = 'error';
            systemHealth.summary = Object.assign(emptySummary(), { total: 1, error: 1 });
            systemHealth.items = [{
                id: 'health-api-error',
                label: '健康检查接口',
                status: 'error',
                message,
                icon: 'fa-triangle-exclamation',
            }];
            systemHealth.progress = 100;
            if (showToast) showToast(`健康检查失败: ${message}`, 'error');
        } finally {
            systemHealth.loading = false;
            clearProgressTimer();
        }
    };

    const openSystemHealth = () => {
        systemHealth.visible = true;
        runSystemHealthCheck();
    };

    const closeSystemHealth = () => {
        systemHealth.visible = false;
        clearProgressTimer();
    };

    const systemHealthHeadline = computed(() => {
        if (systemHealth.loading) return '正在检查...';
        if (systemHealth.status === 'error') return '检查完成，有错误';
        if (systemHealth.status === 'warning') return '检查完成，有提醒';
        if (systemHealth.status === 'ok') return '检查完成';
        return '健康检查';
    });

    const systemHealthMetaText = computed(() => {
        if (systemHealth.loading) return '正在逐项读取系统状态';
        if (systemHealth.error) return systemHealth.error;
        if (!systemHealth.checkedAt) return '等待开始';
        return `${systemHealth.checkedAt.replace('T', ' ')} · ${systemHealth.elapsedMs}ms`;
    });

    const getSystemHealthStatusLabel = (status) => {
        const map = {
            ok: '正常',
            warning: '提醒',
            error: '错误',
            disabled: '未启用',
        };
        return map[status] || '未知';
    };

    const getSystemHealthStatusIcon = (status) => {
        const map = {
            ok: 'fa-circle-check',
            warning: 'fa-circle-exclamation',
            error: 'fa-circle-xmark',
            disabled: 'fa-circle-minus',
        };
        return map[status] || 'fa-circle-question';
    };

    onUnmounted(() => {
        clearProgressTimer();
    });

    return {
        systemHealth,
        systemHealthHeadline,
        systemHealthMetaText,
        openSystemHealth,
        closeSystemHealth,
        runSystemHealthCheck,
        getSystemHealthStatusLabel,
        getSystemHealthStatusIcon,
    };
}
