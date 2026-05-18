import axios from 'axios';
import { computed, reactive, ref, watch } from 'vue';

export function useResourceTransfer({ tab, config302, build302Payload, showToast }) {
    // ==========================================
    // 资源转存
    // ==========================================
    const transferInput = ref('');
    const transferLoading = ref(false);
    const transferResult = ref(null);
    const transferHistory = ref([]);
    const transferPage = ref(1);
    const transferPageSize = ref(12);
    const transferConfig = reactive({ dir: '', drive_index: 0 });
    const transferConfigForm = reactive({ dir: '', drive_index: 0 });
    const transferDirBrowser = reactive({
        visible: false,
        loading: false,
        currentCid: '0',
        currentPath: '/',
        history: [],
        dirs: []
    });
    const transferHistoryStats = computed(() => {
        const total = transferHistory.value.length;
        const success = transferHistory.value.filter((item) => getTransferStatusClass(item) === 'success').length;
        const failed = transferHistory.value.filter((item) => getTransferStatusClass(item) === 'error').length;
        return { total, success, failed };
    });
    const transferDirLabel = computed(() => transferConfigForm.dir || transferConfig.dir || '根目录');
    const transferPageCount = computed(() => Math.max(1, Math.ceil(transferHistory.value.length / transferPageSize.value)));
    const transferHistoryRange = computed(() => {
        const total = transferHistory.value.length;
        if (!total) return { start: 0, end: 0, total };
        const start = (transferPage.value - 1) * transferPageSize.value + 1;
        const end = Math.min(start + transferPageSize.value - 1, total);
        return { start, end, total };
    });
    const paginatedTransferHistory = computed(() => {
        const start = (transferPage.value - 1) * transferPageSize.value;
        return transferHistory.value.slice(start, start + transferPageSize.value);
    });

    const getTransferSourceClass = (itemOrSource = '') => {
        const value = typeof itemOrSource === 'object'
            ? [
                itemOrSource.source_key,
                itemOrSource.source_kind,
                itemOrSource.source_label,
                itemOrSource.source
            ].filter(Boolean).join(' ').toLowerCase()
            : String(itemOrSource || '').toLowerCase();
        if (value.includes('telegram_bot') || value.includes('机器人')) return 'telegram-bot';
        if (value.includes('telegram_monitor') || value.includes('监听')) return 'telegram-monitor';
        if (value.includes('telegram')) return 'telegram';
        if (value.includes('微信') || value.includes('wechat')) return 'wechat';
        if (value.includes('手动') || value.includes('manual')) return 'manual';
        return 'default';
    };

    const getTransferSourceText = (item = {}) => item.source_label || item.source || '未知';
    const getTransferSourceDetail = (item = {}) => item.source_detail || item.channel_title || item.chat_title || '';

    function getTransferStatusClass(item = {}) {
        const status = String(item.status || '').toLowerCase();
        if (item.success === true || status.includes('成功') || status.includes('已添加')) return 'success';
        if (item.success === false || status.includes('失败') || status.includes('错误')) return 'error';
        return 'info';
    }

    const setTransferPage = (page) => {
        const next = Number(page) || 1;
        transferPage.value = Math.min(Math.max(next, 1), transferPageCount.value);
    };

    const loadTransferConfig = () => {
        if (config302.drives && config302.drives.length > 0) {
            transferConfig.dir = config302.drives[0].transfer_dir || '';
            transferConfig.drive_index = 0;
            transferConfigForm.dir = transferConfig.dir;
            transferConfigForm.drive_index = 0;
        }
    };

    const loadTransferDir = async (cid = '0', path = '/') => {
        transferDirBrowser.loading = true;
        try {
            const res = await axios.post('/api/drive115_upload/browse115', { cid, drive_index: 0 });
            if (res.data?.status === 'ok') {
                transferDirBrowser.dirs = res.data.dirs || [];
                transferDirBrowser.currentCid = String(cid || '0');
                transferDirBrowser.currentPath = path || '/';
            } else {
                showToast(res.data?.message || '读取目录失败', 'error');
            }
        } catch (e) {
            showToast('浏览失败: ' + e.message, 'error');
        } finally {
            transferDirBrowser.loading = false;
        }
    };

    const browseTransferDir = () => {
        if (transferDirBrowser.visible) {
            transferDirBrowser.visible = false;
            return;
        }
        transferDirBrowser.visible = true;
        transferDirBrowser.history.splice(0);
        loadTransferDir('0', '/');
    };

    const selectTransferDir = (dir) => {
        transferDirBrowser.history.push({ cid: transferDirBrowser.currentCid, path: transferDirBrowser.currentPath });
        const nextPath = transferDirBrowser.currentPath === '/' ? `/${dir.name}` : `${transferDirBrowser.currentPath}/${dir.name}`;
        loadTransferDir(dir.cid, nextPath);
    };

    const transferDirUp = () => {
        const prev = transferDirBrowser.history.pop();
        if (!prev) return;
        loadTransferDir(prev.cid, prev.path);
    };

    const applyTransferDir = () => {
        if (!transferDirBrowser.currentCid || transferDirBrowser.currentCid === '0') return showToast('不能选择根目录，留空即使用根目录', 'error');
        transferConfigForm.dir = transferDirBrowser.currentPath;
        transferDirBrowser.visible = false;
        transferDirBrowser.dirs = [];
        transferDirBrowser.history = [];
        showToast('已选择转存目录', 'success');
    };

    const saveTransferConfig = async () => {
        if (config302.drives && config302.drives.length > 0) {
            config302.drives[0].transfer_dir = transferConfigForm.dir;
            config302.drives[0].transfer_drive_index = 0;
        }
        try {
            const payload = build302Payload();
            await axios.post('/api/config_302/save', payload);
            transferConfig.dir = transferConfigForm.dir;
            transferConfig.drive_index = 0;
            transferConfigForm.drive_index = 0;
            showToast('转存配置已保存', 'success');
        } catch (e) {
            showToast('保存失败: ' + (e.response?.data?.detail || e.message), 'error');
        }
    };

    const manualTransfer = async () => {
        const link = transferInput.value.trim();
        if (!link) return;
        transferLoading.value = true;
        transferResult.value = null;
        try {
            const res = await axios.post('/api/transfer/manual', { link });
            transferResult.value = res.data;
            transferInput.value = '';
            loadTransferHistory();
        } catch (e) {
            transferResult.value = { success: false, message: e.response?.data?.detail || '转存请求失败' };
        } finally {
            transferLoading.value = false;
        }
    };

    const loadTransferHistory = async () => {
        try {
            const res = await axios.get('/api/transfer/history');
            transferHistory.value = res.data || [];
            setTransferPage(transferPage.value);
        } catch { /* ignore */ }
    };

    const clearTransferHistory = async () => {
        if (!confirm('确定要清空所有转存记录吗？')) return;
        try {
            await axios.delete('/api/transfer/history');
            transferHistory.value = [];
            transferPage.value = 1;
        } catch { /* ignore */ }
    };

    // tab 切换时自动加载转存数据
    watch(tab, (v) => {
        if (v === 'resource_transfer') {
            loadTransferConfig();
            loadTransferHistory();
        }
    }, { immediate: true });

    // 302 配置加载后同步转存配置
    watch(() => config302.drives, () => loadTransferConfig(), { deep: true });
    watch([() => transferHistory.value.length, transferPageSize], () => {
        setTransferPage(transferPage.value);
    });

    return {
        transferInput,
        transferLoading,
        transferResult,
        transferHistory,
        transferHistoryStats,
        transferPage,
        transferPageSize,
        transferPageCount,
        transferHistoryRange,
        paginatedTransferHistory,
        transferConfig,
        transferConfigForm,
        transferDirLabel,
        transferDirBrowser,
        getTransferSourceClass,
        getTransferSourceText,
        getTransferSourceDetail,
        getTransferStatusClass,
        setTransferPage,
        loadTransferConfig,
        loadTransferHistory,
        browseTransferDir,
        selectTransferDir,
        transferDirUp,
        applyTransferDir,
        saveTransferConfig,
        clearTransferHistory,
        manualTransfer,
    };
}
