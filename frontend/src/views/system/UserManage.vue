<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search, Edit, Delete, UserFilled } from '@element-plus/icons-vue'

// ---------- 筛选与分页 ----------
const keyword = ref('')
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const loading = ref(false)

// ---------- 角色映射 ----------
const roleMap = {
  1: { label: '管理员', tagType: 'danger' },
  2: { label: '普通用户', tagType: 'info' },
}

// ---------- Mock 数据（接口通了以后删除） ----------
let mockId = 9
const mockUsers = [
  { id: 1, username: 'admin', nickname: '系统管理员', email: 'admin@example.com', phone: '13800000001', roleId: 1, createdAt: '2026-01-01 09:00:00' },
  { id: 2, username: 'zhangsan', nickname: '张三', email: 'zhangsan@example.com', phone: '13800000002', roleId: 2, createdAt: '2026-02-14 11:20:33' },
  { id: 3, username: 'lisi', nickname: '李四', email: 'lisi@example.com', phone: '13800000003', roleId: 2, createdAt: '2026-02-20 15:41:09' },
  { id: 4, username: 'wangwu', nickname: '王五', email: 'wangwu@example.com', phone: '13800000004', roleId: 2, createdAt: '2026-03-05 10:12:47' },
  { id: 5, username: 'zhaoliu', nickname: '赵六', email: 'zhaoliu@example.com', phone: '13800000005', roleId: 2, createdAt: '2026-03-18 09:33:28' },
  { id: 6, username: 'sunqi', nickname: '孙七', email: 'sunqi@example.com', phone: '13800000006', roleId: 2, createdAt: '2026-04-02 14:05:16' },
  { id: 7, username: 'zhouba', nickname: '周八', email: 'zhouba@example.com', phone: '13800000007', roleId: 2, createdAt: '2026-04-21 16:54:02' },
  { id: 8, username: 'wujiu', nickname: '吴九', email: 'wujiu@example.com', phone: '13800000008', roleId: 2, createdAt: '2026-05-01 08:27:55' },
]

const users = ref([])

// ---------- 加载列表 ----------
async function loadUsers() {
  loading.value = true
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // const res = await getUserList({
    //   pageNum: pageNum.value,
    //   pageSize: pageSize.value,
    //   keyword: keyword.value || undefined,
    // })
    // users.value = res.list || []
    // total.value = res.total || 0
    await new Promise((resolve) => setTimeout(resolve, 300))

    // Mock 筛选 + 分页
    let list = [...mockUsers]
    if (keyword.value) {
      list = list.filter(
        (item) =>
          item.username.includes(keyword.value) || item.nickname.includes(keyword.value)
      )
    }
    total.value = list.length
    const startIdx = (pageNum.value - 1) * pageSize.value
    users.value = list.slice(startIdx, startIdx + pageSize.value)
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pageNum.value = 1
  loadUsers()
}

// 多选
const selectedRows = ref([])
function handleSelectionChange(rows) {
  selectedRows.value = rows
}

// ---------- 新增/编辑弹窗 ----------
const dialogVisible = ref(false)
const dialogTitle = computed(() => (isEdit.value ? '编辑用户' : '新增用户'))
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref(null)

const form = reactive({
  id: null,
  username: '',
  password: '',
  nickname: '',
  email: '',
  phone: '',
  roleId: 2,
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度为 3-20 个字符', trigger: 'blur' },
  ],
  password: [
    {
      // 新增必填，编辑选填
      validator: (rule, value, callback) => {
        if (!isEdit.value && !value) {
          callback(new Error('请输入密码'))
        } else if (value && (value.length < 6 || value.length > 20)) {
          callback(new Error('密码长度为 6-20 个字符'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }],
  phone: [
    { pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' },
  ],
}

function openCreate() {
  isEdit.value = false
  Object.assign(form, {
    id: null,
    username: '',
    password: '',
    nickname: '',
    email: '',
    phone: '',
    roleId: 2,
  })
  dialogVisible.value = true
}

function openEdit(row) {
  isEdit.value = true
  Object.assign(form, {
    id: row.id,
    username: row.username,
    password: '',
    nickname: row.nickname,
    email: row.email,
    phone: row.phone,
    roleId: row.roleId,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // if (isEdit.value) {
    //   await updateUser(form.id, { ...form, password: form.password || undefined })
    // } else {
    //   await createUser({ ...form })
    // }
    await new Promise((resolve) => setTimeout(resolve, 500))

    // Mock 写入
    if (isEdit.value) {
      const idx = mockUsers.findIndex((item) => item.id === form.id)
      if (idx > -1) {
        mockUsers[idx] = {
          ...mockUsers[idx],
          username: form.username,
          nickname: form.nickname,
          email: form.email,
          phone: form.phone,
          roleId: form.roleId,
        }
      }
      ElMessage.success('编辑成功')
    } else {
      mockUsers.unshift({
        id: mockId++,
        username: form.username,
        nickname: form.nickname || form.username,
        email: form.email,
        phone: form.phone,
        roleId: form.roleId,
        createdAt: new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-'),
      })
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    loadUsers()
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    submitting.value = false
  }
}

// ---------- 分配角色弹窗 ----------
const roleDialogVisible = ref(false)
const roleFormRef = ref(null)
const roleSubmitting = ref(false)
const roleForm = reactive({ userId: null, username: '', roleId: 2 })

function openAssignRole(row) {
  roleForm.userId = row.id
  roleForm.username = row.username
  roleForm.roleId = row.roleId
  roleDialogVisible.value = true
}

async function handleAssignRole() {
  roleSubmitting.value = true
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // await assignRole({ userId: roleForm.userId, roleId: roleForm.roleId })
    await new Promise((resolve) => setTimeout(resolve, 500))

    const target = mockUsers.find((item) => item.id === roleForm.userId)
    if (target) target.roleId = roleForm.roleId
    ElMessage.success('角色分配成功')
    roleDialogVisible.value = false
    loadUsers()
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    roleSubmitting.value = false
  }
}

// ---------- 删除 ----------
async function handleDelete(row) {
  // 接口未通前用 Mock 占位，接口通了以后替换为：
  // await deleteUser(row.id)
  await new Promise((resolve) => setTimeout(resolve, 300))
  const idx = mockUsers.findIndex((item) => item.id === row.id)
  if (idx > -1) mockUsers.splice(idx, 1)
  ElMessage.success('删除成功')
  loadUsers()
}

onMounted(loadUsers)
</script>

<template>
  <div class="user-manage">
    <!-- 顶部操作栏 -->
    <el-card shadow="hover" class="toolbar-card">
      <div class="toolbar">
        <el-button type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
        <div class="search-bar">
          <el-input
            v-model="keyword"
            placeholder="按用户名/昵称搜索"
            clearable
            :prefix-icon="Search"
            style="width: 240px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
        </div>
      </div>
    </el-card>

    <!-- 用户列表 -->
    <el-card shadow="hover">
      <el-table
        :data="users"
        v-loading="loading"
        stripe
        border
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" align="center" />
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="username" label="用户名" width="130" />
        <el-table-column prop="nickname" label="昵称" width="130" />
        <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip />
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column label="角色" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="roleMap[row.roleId]?.tagType || 'info'">
              {{ roleMap[row.roleId]?.label || '未知' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="170" align="center" />
        <el-table-column label="操作" width="220" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="openEdit(row)">编辑</el-button>
            <el-button type="warning" link :icon="UserFilled" @click="openAssignRole(row)">
              分配角色
            </el-button>
            <el-popconfirm title="确定删除该用户吗？" @confirm="handleDelete(row)">
              <template #reference>
                <el-button type="danger" link :icon="Delete">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pageNum"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="loadUsers"
          @size-change="handleSearch"
        />
      </div>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名（3-20字符）" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="isEdit ? '不修改请留空' : '请输入密码（6-20字符）'"
          />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="form.nickname" placeholder="请输入昵称" maxlength="20" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" maxlength="11" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.roleId" style="width: 100%">
            <el-option label="管理员" :value="1" />
            <el-option label="普通用户" :value="2" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 分配角色弹窗 -->
    <el-dialog v-model="roleDialogVisible" title="分配角色" width="420px" destroy-on-close>
      <el-form ref="roleFormRef" :model="roleForm" label-width="80px">
        <el-form-item label="用户">
          <el-input v-model="roleForm.username" disabled />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="roleForm.roleId" style="width: 100%">
            <el-option label="管理员" :value="1" />
            <el-option label="普通用户" :value="2" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="roleSubmitting" @click="handleAssignRole">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.user-manage {
  .toolbar-card {
    margin-bottom: 16px;

    .toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 12px;

      .search-bar {
        display: flex;
        gap: 8px;
      }
    }
  }

  .pagination {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }
}
</style>
