<template>
  <div class="exam-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>考试列表</span>
          <el-button
            v-if="isTeacher"
            type="primary"
            @click="showCreateDialog = true"
          >
            创建考试
          </el-button>
        </div>
      </template>

      <el-table :data="exams" style="width: 100%" v-loading="loading">
        <el-table-column prop="title" label="考试名称" min-width="200" />
        <el-table-column prop="description" label="描述" min-width="250" show-overflow-tooltip />
        <el-table-column prop="start_time" label="开始时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.start_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="duration_minutes" label="时长" width="100">
          <template #default="{ row }">
            {{ row.duration_minutes }} 分钟
          </template>
        </el-table-column>
        <el-table-column prop="total_score" label="总分" width="80">
          <template #default="{ row }">
            {{ row.total_score }} 分
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="viewExam(row)">
              查看
            </el-button>
            <el-button type="success" size="small" @click="startExam(row)" v-if="row.is_published">
              参加
            </el-button>
            <template v-if="isTeacher">
              <el-button type="warning" size="small" @click="editExam(row)">
                编辑
              </el-button>
              <el-button type="danger" size="small" @click="deleteExam(row)">
                删除
              </el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="exams.length === 0 && !loading" description="暂无考试" />
    </el-card>

    <!-- 创建/编辑考试对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="isEditing ? '编辑考试' : '创建考试'"
      width="600px"
    >
      <el-form :model="examForm" label-width="100px">
        <el-form-item label="考试名称">
          <el-input v-model="examForm.title" placeholder="请输入考试名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="examForm.description"
            type="textarea"
            rows="3"
            placeholder="请输入考试描述"
          />
        </el-form-item>
        <el-form-item label="开始时间">
          <el-date-picker
            v-model="examForm.start_time"
            type="datetime"
            placeholder="选择开始时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-date-picker
            v-model="examForm.end_time"
            type="datetime"
            placeholder="选择结束时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="考试时长">
          <el-input-number v-model="examForm.duration_minutes" :min="1" :max="300" />
          <span style="margin-left: 8px">分钟</span>
        </el-form-item>
        <el-form-item label="总分">
          <el-input-number v-model="examForm.total_score" :min="1" :max="1000" />
          <span style="margin-left: 8px">分</span>
        </el-form-item>
        <el-form-item label="及格分数">
          <el-input-number v-model="examForm.pass_score" :min="0" :max="examForm.total_score" />
          <span style="margin-left: 8px">分</span>
        </el-form-item>
        <el-form-item label="发布">
          <el-switch v-model="examForm.is_published" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveExam" :loading="saving">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/store/auth'
import { examApi, submissionApi } from '@/api'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const saving = ref(false)
const exams = ref([])
const showCreateDialog = ref(false)
const isEditing = ref(false)
const editingId = ref(null)

const isTeacher = computed(() => authStore.isTeacher)

const examForm = ref({
  title: '',
  description: '',
  start_time: null,
  end_time: null,
  duration_minutes: 60,
  total_score: 100,
  pass_score: 60,
  is_published: false
})

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}

const loadExams = async () => {
  loading.value = true
  try {
    exams.value = await examApi.getList()
  } catch (error) {
    ElMessage.error('加载考试列表失败')
  } finally {
    loading.value = false
  }
}

const viewExam = (exam) => {
  router.push(`/exams/${exam.id}`)
}

const startExam = async (exam) => {
  try {
    await submissionApi.startExam(exam.id)
    router.push(`/exams/${exam.id}/take`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '开始考试失败')
  }
}

const editExam = (exam) => {
  isEditing.value = true
  editingId.value = exam.id
  examForm.value = { ...exam }
  showCreateDialog.value = true
}

const saveExam = async () => {
  saving.value = true
  try {
    if (isEditing.value) {
      await examApi.update(editingId.value, examForm.value)
      ElMessage.success('考试更新成功')
    } else {
      await examApi.create(examForm.value)
      ElMessage.success('考试创建成功')
    }
    showCreateDialog.value = false
    resetForm()
    loadExams()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const deleteExam = async (exam) => {
  try {
    await ElMessageBox.confirm('确定要删除该考试吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await examApi.delete(exam.id)
    ElMessage.success('删除成功')
    loadExams()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

const resetForm = () => {
  examForm.value = {
    title: '',
    description: '',
    start_time: null,
    end_time: null,
    duration_minutes: 60,
    total_score: 100,
    pass_score: 60,
    is_published: false
  }
  isEditing.value = false
  editingId.value = null
}

onMounted(() => {
  loadExams()
})
</script>

<style scoped>
.exam-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
