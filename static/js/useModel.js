import { API_BASE } from './api.js';
// 模型选择模块
export function useModel() {
    const { ref, computed } = Vue;
    const { ElMessage } = ElementPlus;

    const providers = ref([]);
    const currentModelId = ref('');
    const currentModelLabel = computed(() => {
        const p = providers.value.find(x => x.id === currentModelId.value);
        return p ? p.name + ' · ' + p.display_name : '';
    });

    const modelGroups = computed(() => {
        const groups = {};
        for (const p of providers.value) {
            if (!groups[p.name]) groups[p.name] = { name: p.name, models: [] };
            groups[p.name].models.push({ id: p.id, display_name: p.display_name });
        }
        return Object.values(groups);
    });

    function splitModelId() {
        const id = currentModelId.value || '';
        const idx = id.indexOf('/');
        if (idx > 0) return { provider: id.substring(0, idx), model: id.substring(idx + 1) };
        return { provider: id, model: '' };
    }

    async function loadProviders() {
        try {
            const { data } = await axios.get(API_BASE + '/api/providers');
            if (data.success && data.data) {
                providers.value = data.data;
                const active = data.data.find(p => p.active) || data.data[0];
                if (active) currentModelId.value = active.id;
            }
        } catch (e) {
            console.error('加载模型列表失败', e);
        }
    }

    function onModelChange(val) {
        ElMessage.success('已切换到：' + currentModelLabel.value);
    }

    return { providers, currentModelId, currentModelLabel, modelGroups, loadProviders, onModelChange, splitModelId };
}
