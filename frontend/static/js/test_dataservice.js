class DataService {
  static async getPhotos() {
    try {
      let saved = localStorage.getItem("photos");
      if (saved) {
        const parsed = JSON.parse(saved);
        return Array.isArray(parsed) ? parsed : PHOTO_DATA;
      }
      localStorage.setItem("photos", JSON.stringify(PHOTO_DATA));
      return PHOTO_DATA;
    } catch (e) {
      return PHOTO_DATA;
    }
  }
  static async getPhoto(id) {
    const photos = await this.getPhotos();
    return photos.find(p => p.id == id) || null;
  }
  static async addPhoto(photo) {
    const photos = await this.getPhotos();
    const newId = photos.length > 0 ? Math.max(...photos.map(p => p.id)) + 1 : 1;
    photo.id = newId;
    photos.push(photo);
    localStorage.setItem("photos", JSON.stringify(photos));
    return photo;
  }
}