<template>
  <div class="user-manage">
    <el-card>
      <template #header>
        <span>用户管理</span>
      </template>

      <el-table :data="users" style="width: 100%" v-loading="loading">
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="full_name" label="姓名" />
        <el-table-column prop="email" label="邮箱" />
        <el-table-column prop="role" label="角色">
          <template #default="{ row }">
            <el-tag :type="getRoleType(row.role)">{{ getRoleLabel(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">{{ row.is_active ? '正常' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
      </el-table>

      <el-empty v-if="users.length === 0 && !loading" description="暂无用户" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { userApi } from '@/api'

const loading = ref(false)
const users = ref([])

const formatDate = (date) => date ? new Date(date).toLocaleString('zh-CN') : '-'

const getRoleLabel = (role) => {
  const roles = { student: '学生', teacher: '教师', admin: '管理员' }
  return roles[role] || role
}

const getRoleType = (role) => {
  const types = { student: 'info', teacher: 'warning', admin: 'danger' }
  return types[role] || ''
}

const loadUsers = async () => {
  loading.value = true
  try { users.value = await userApi.getList() } 
  catch { ElMessage.error('加载用户列表失败') } 
  finally { loading.value = false }
}

onMounted(() => { loadUsers() })
</script>

<style scoped>
.user-manage { padding: 20px; }
</style>
