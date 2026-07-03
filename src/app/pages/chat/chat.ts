import { AfterViewChecked, Component, ElementRef, HostListener, OnDestroy, OnInit, ViewChild, WritableSignal, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ChatService } from '../../services/chat.services';
import { AuthService } from '../../services/auth.services';
import { RoomService, AppUser, Room, ChatMessage, PdfInfo } from '../../services/room.services';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './chat.html',
  styleUrl: './chat.css',
})
export class Chat implements OnInit, OnDestroy, AfterViewChecked {

  @ViewChild('messagesContainer') private messagesContainer!: ElementRef<HTMLDivElement>;
  private shouldScrollToBottom = false;

  message = '';

  messages    = signal<ChatMessage[]>([]);
  users       = signal<AppUser[]>([]);
  myRooms     = signal<Room[]>([]);
  selectedRoom = signal<Room | null>(null);
  unread      = signal<Record<string, number>>({});

  showNewGroup    = signal(false);
  newGroupName    = '';
  selectedMembers = signal<Set<string>>(new Set());

  showAddMembers      = signal(false);
  addMembersSelected  = signal<Set<string>>(new Set());

  showAddUser  = signal(false);
  addUserEmail = '';
  addUserMsg   = signal<string | null>(null);

  aiEnabled       = signal(false);
  showGroups      = signal(false);
  showContacts    = signal(false);
  showMobileMenu  = signal(false);
  isMobile        = signal(window.innerWidth <= 768);

  pdfUploading = signal(false);
  pdfStatus    = signal<string | null>(null);

  @HostListener('window:resize')
  onResize() { this.isMobile.set(window.innerWidth <= 768); }

  private pollTimer?: ReturnType<typeof setInterval>;
  private seenCids = new Set<string>();
  private palette  = ['#f72585','#7209b7','#3a0ca3','#4361ee','#4cc9f0','#06d6a0','#ff9e00','#ef476f'];

  constructor(
    protected chatService: ChatService,
    protected authService: AuthService,
    protected roomService: RoomService,
    private   router: Router,
  ) {}

  ngAfterViewChecked() {
    if (this.shouldScrollToBottom) {
      this.shouldScrollToBottom = false;
      try {
        const el = this.messagesContainer?.nativeElement;
        if (el) el.scrollTop = el.scrollHeight;
      } catch {}
    }
  }

  ngOnInit() {
    const uid = this.authService.user()?.uid;
    if (!uid) return;

    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }

    this.chatService.connect(uid, (msg: any) => this.onLiveMessage(msg));
    this.refresh();
    this.pollTimer = setInterval(() => this.refresh(), 6000);
  }

  ngOnDestroy() {
    this.chatService.disconnect();
    if (this.pollTimer) clearInterval(this.pollTimer);
  }

  // ─── Datos ────────────────────────────────────────────────────────────────

  private async refresh() {
    const uid = this.authService.user()?.uid;
    if (!uid) return;
    try {
      const [users, rooms] = await Promise.all([
        this.roomService.getUsers(),
        this.roomService.getMyRooms(uid),
      ]);
      this.users.set(users);
      this.myRooms.set(rooms);
    } catch {}
  }

  // ─── Mensajes en vivo ─────────────────────────────────────────────────────

  private onLiveMessage(msg: any) {
    const room = this.selectedRoom();

    // Sala eliminada
    if (msg.type === 'deleted') {
      this.myRooms.update(list => list.filter(r => r.id !== msg.roomId));
      if (room?.id === msg.roomId) {
        this.selectedRoom.set(null);
        this.messages.set([]);
      }
      return;
    }

    // Mensaje de otra sala → contador + notificación
    if (!room || msg.roomId !== room.id) {
      if (msg.type !== 'delete') {
        this.unread.update(u => ({ ...u, [msg.roomId]: (u[msg.roomId] || 0) + 1 }));
        this.showNotification(msg);
      }
      return;
    }

    // Borrado de mensaje en la sala activa
    if (msg.type === 'delete') {
      this.seenCids.delete(msg.cid);
      this.messages.update(list => list.filter(m => m.cid !== msg.cid));
      return;
    }

    // Deduplicar
    if (this.seenCids.has(msg.cid)) return;
    this.seenCids.add(msg.cid);

    // Mensaje normal en la sala activa
    this.messages.update(list => [...list, msg]);
    this.unread.update(u => ({ ...u, [msg.roomId]: 0 }));
    this.shouldScrollToBottom = true;

    // Notificar si la pestaña no tiene foco
    if (!document.hasFocus()) {
      this.showNotification(msg);
    }
  }

  private showNotification(msg: any) {
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    if (!msg.text) return;
    new Notification(msg.senderName || 'Nuevo mensaje', {
      body: msg.text,
      icon: '/favicon.ico',
    });
  }

  // ─── Sala ─────────────────────────────────────────────────────────────────

  async selectRoom(room: Room) {
    this.selectedRoom.set(room);
    this.aiEnabled.set(room.aiEnabled ?? false);
    this.pdfStatus.set(null);
    this.pdfList.set([]);
    this.seenCids.clear();
    this.unread.update(u => ({ ...u, [room.id]: 0 }));

    const history = await this.roomService.loadMessages(room.id);
    history.forEach(m => this.seenCids.add(m.cid));
    this.messages.set(history);
    this.shouldScrollToBottom = true;

    if (room.id.startsWith('ai__')) {
      await this.loadPdfs(room.id);
    }
  }

  async deleteCurrentChat() {
    const room = this.selectedRoom();
    if (!room) return;
    if (!confirm('¿Eliminar este chat para todos?')) return;

    try {
      await this.roomService.deleteRoom(room.id);
      this.myRooms.update(list => list.filter(r => r.id !== room.id));
      this.selectedRoom.set(null);
      this.messages.set([]);
    } catch (e) {
      console.error(e);
    }
  }

  // ─── Mensajes ─────────────────────────────────────────────────────────────

  sendMessage() {
    const text = this.message.trim();
    const room = this.selectedRoom();
    const me   = this.currentUser();
    if (!text || !room || !me) return;

    const msg: ChatMessage = {
      cid:        crypto.randomUUID(),
      roomId:     room.id,
      text,
      senderUid:  me.uid,
      senderName: me.displayName,
    };

    this.seenCids.add(msg.cid);
    this.messages.update(list => [...list, msg]);
    this.message = '';
    this.shouldScrollToBottom = true;
    this.chatService.send(msg);
  }

  deleteMessage(msg: ChatMessage) {
    const me = this.currentUser();
    if (!me || msg.senderUid !== me.uid) return;

    this.chatService.send({ type: 'delete', cid: msg.cid, roomId: msg.roomId, senderUid: me.uid });
    this.seenCids.delete(msg.cid);
    this.messages.update(list => list.filter(m => m.cid !== msg.cid));
  }

  // ─── Grupos ───────────────────────────────────────────────────────────────

  async createGroup() {
    const me = this.currentUser();
    if (!me) return;
    const name = this.newGroupName.trim();
    if (!name) return;

    const room = await this.roomService.createGroup(name, [me.uid, ...this.selectedMembers()]);
    this.showNewGroup.set(false);
    this.newGroupName = '';
    this.selectedMembers.set(new Set());
    await this.refresh();
    await this.selectRoom(room);
  }

  async addMembersToGroup() {
    const room = this.selectedRoom();
    if (!room) return;
    const members = [...this.addMembersSelected()];
    if (members.length === 0) return;

    const updated = await this.roomService.addGroupMembers(room.id, members);
    this.selectedRoom.set({ ...room, members: updated.members });
    this.addMembersSelected.set(new Set());
    this.showAddMembers.set(false);
    await this.refresh();
  }

  async leaveGroup() {
    const room = this.selectedRoom();
    const me   = this.currentUser();
    if (!room || !me) return;

    await this.roomService.leaveGroup(room.id, me.uid);
    this.selectedRoom.set(null);
    this.messages.set([]);
    await this.refresh();
  }

  // ─── PDF / RAG ────────────────────────────────────────────────────────────

  pdfList = signal<PdfInfo[]>([]);

  async loadPdfs(roomId: string) {
    try {
      const { pdfs } = await this.roomService.listPdfs(roomId);
      this.pdfList.set(pdfs);
    } catch {
      this.pdfList.set([]);
    }
  }

  async uploadPdf(event: Event) {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    if (!files.length) return;
    const room = this.selectedRoom();
    if (!room) return;

    this.pdfUploading.set(true);
    this.pdfStatus.set(null);
    try {
      for (const file of files) {
        try {
          const result = await this.roomService.uploadPdf(room.id, file);
          this.pdfStatus.set(`✓ ${result.filename} · ${result.chunks} fragmentos · PDF ${result.totalPdfs}/${result.maxPdfs}`);
        } catch (e: any) {
          this.pdfStatus.set(`✗ ${file.name}: ${e?.message ?? 'Error al procesar el PDF'}`);
          break; // Si uno falla (ej. límite alcanzado), no sigue con el resto.
        }
      }
    } finally {
      this.pdfUploading.set(false);
      input.value = '';
      await this.loadPdfs(room.id);
    }
  }

  async deletePdf(docId: string) {
    const room = this.selectedRoom();
    if (!room) return;
    try {
      const { pdfs } = await this.roomService.deletePdf(room.id, docId);
      this.pdfList.set(pdfs);
      this.pdfStatus.set(null);
    } catch (e: any) {
      this.pdfStatus.set(`✗ ${e?.message ?? 'No se pudo borrar el PDF'}`);
    }
  }

  // ─── IA ───────────────────────────────────────────────────────────────────

  async openAiChat() {
    const me = this.currentUser();
    if (!me) return;

    const existingAiRoom = this.myRooms().find(r => r.id === `ai__${me.uid}`);
    if (existingAiRoom) {
      await this.selectRoom(existingAiRoom);
      return;
    }

    const room = await this.roomService.openAiChat(me.uid);
    this.myRooms.update(list => [...list, room]);
    await this.selectRoom(room);
  }

  async toggleRoomAI() {
    const room = this.selectedRoom();
    if (!room) return;
    try {
      const res = await this.roomService.toggleRoomAI(room.id);
      this.aiEnabled.set(res.aiEnabled);
      this.selectedRoom.set({ ...room, aiEnabled: res.aiEnabled });
      this.myRooms.update(list =>
        list.map(r => r.id === room.id ? { ...r, aiEnabled: res.aiEnabled } : r)
      );
    } catch (e) {
      console.error(e);
    }
  }

  // ─── Usuarios / DM ────────────────────────────────────────────────────────

  async openDmWith(other: AppUser) {
    const me = this.currentUser();
    if (!me) return;

    const room = await this.roomService.openDm(me, other);
    await this.refresh();
    await this.selectRoom(room);
  }

  async addUser() {
    const email = this.addUserEmail.trim().toLowerCase();
    if (!email) return;

    const users = await this.roomService.getUsers();
    const found = users.find(u => u.email.toLowerCase() === email);

    if (!found) {
      this.addUserMsg.set('Usuario no encontrado');
      return;
    }

    await this.openDmWith(found);
    this.addUserEmail = '';
    this.addUserMsg.set(null);
    this.showAddUser.set(false);
  }

  // ─── Helpers de UI ────────────────────────────────────────────────────────

  dmUnread(otherUid: string): number {
    const myUid = this.authService.user()?.uid;
    if (!myUid) return 0;
    const roomId = 'dm__' + [myUid, otherUid].sort().join('__');
    return this.unread()[roomId] || 0;
  }

  roomTitle(room: Room): string {
    if (room.type === 'group') return room.name;
    const myUid    = this.authService.user()?.uid;
    const otherUid = room.members.find(uid => uid !== myUid);
    return this.users().find(u => u.uid === otherUid)?.displayName ?? 'Chat';
  }

  roomPhoto(room: Room): string | null {
    if (room.type === 'group') return null;
    const myUid    = this.authService.user()?.uid;
    const otherUid = room.members.find(uid => uid !== myUid);
    const other    = this.users().find(u => u.uid === otherUid);
    return this.roomService.photoSrc(other?.photoUrl);
  }

  avatarColor(seed: string): string {
    let hash = 0;
    for (let i = 0; i < seed.length; i++) {
      hash = seed.charCodeAt(i) + ((hash << 5) - hash);
    }
    return this.palette[Math.abs(hash) % this.palette.length];
  }

  // Toggle genérico reutilizado para miembros de grupo y añadir miembros
  toggleInSet(signal: WritableSignal<Set<string>>, uid: string) {
    signal.update(set => {
      const next = new Set(set);
      next.has(uid) ? next.delete(uid) : next.add(uid);
      return next;
    });
  }

  logout() {
    this.authService.logout();
    this.router.navigate(['/login']);
  }

  private currentUser(): AppUser | null {
    const u = this.authService.user();
    if (!u) return null;
    return { uid: u.uid, email: u.email ?? '', displayName: u.displayName ?? '', online: true };
  }

  // ─── Computados ───────────────────────────────────────────────────────────

  contacts = computed(() =>
    this.users().filter(u => u.uid !== this.authService.user()?.uid && u.uid !== 'ai-bot')
  );

  groups = computed(() =>
    this.myRooms().filter(r => r.type === 'group')
  );

  aiRoom = computed(() => {
    const me = this.authService.user()?.uid;
    return me ? this.myRooms().find(r => r.id === `ai__${me}`) ?? null : null;
  });

  myPhoto = computed(() => {
    const me = this.users().find(u => u.uid === this.authService.user()?.uid);
    return this.roomService.photoSrc(me?.photoUrl);
  });

  nonMembers = computed(() => {
    const room = this.selectedRoom();
    if (!room || room.type !== 'group') return [];
    return this.contacts().filter(c => !room.members.includes(c.uid));
  });
}
