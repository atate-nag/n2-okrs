# N2 Group OKR Dashboard

## Deploy to GitHub Pages (2 minutes)

1. Go to [github.com](https://github.com) and sign in
2. Click **+** → **New repository**
3. Name it `n2-okrs` (or anything you like)
4. Keep it **Public** (required for free GitHub Pages)
5. Click **Create repository**
6. Click **"uploading an existing file"** link
7. Drag both `index.html` and this `README.md` into the upload area
8. Click **Commit changes**
9. Go to **Settings** → **Pages** (in left sidebar)
10. Under "Source", select **main** branch, click **Save**
11. Wait ~60 seconds, then visit: `https://YOUR-USERNAME.github.io/n2-okrs/`

## First use

1. Open your new GitHub Pages URL
2. Click **"Create Cloud Storage"** 
3. Copy the Blob ID that appears
4. Share that Blob ID with anyone who needs to edit

## For other editors

They need to set the same Blob ID. They can either:
- Open browser console (F12) and run: `localStorage.setItem('n2_jsonblob_id', 'YOUR_BLOB_ID'); location.reload();`
- Or you can ask me to bake the ID into the HTML so it's automatic

## Notes

- Data is stored on jsonblob.com (free, no account needed)
- Anyone with the URL can view
- Anyone with the Blob ID can edit
- Changes sync automatically
